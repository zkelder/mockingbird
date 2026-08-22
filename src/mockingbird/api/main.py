"""FastAPI app for the MockingBird product API."""

from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from hashlib import sha1
import json
from math import ceil
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any, Mapping
import uuid

import numpy as np
import cv2

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, Response, StreamingResponse

from mockingbird import __version__ as APP_VERSION
from mockingbird.api.schemas import (
    AnalyticsSummary,
    AlertCategory,
    ActivityLibraryExportSelectionRequest,
    ActivityLibraryExportSelectionResponse,
    ActivityLibrarySavedView,
    ActivityLibrarySavedViewCreate,
    ActivityLibrarySavedViewUpdate,
    ActivityLibrarySearchRequest,
    ActivityLibrarySearchResponse,
    AdapterEvaluationSummary,
    CameraSource,
    CameraSourceCreate,
    CameraSourceCreateResponse,
    CameraSourceMutationResult,
    CameraSourceUpdate,
    CameraConfigurationApplyRequest,
    CameraConfigurationApplyResponse,
    CameraConfigurationEditResponse,
    CameraConfigurationHistoryResponse,
    CameraConfigurationImpactPreview,
    CameraConfigurationImpactPreviewRequest,
    CameraConfigurationSecretAction,
    CameraNodeAdvertisedCamera,
    CameraNodeCaptureProfile,
    CameraNodePairRequest,
    CameraNodePairResponse,
    CameraNodePendingSetupDraftUpdate,
    CameraNodePendingSetupResponse,
    CameraNodePendingSetupRevokeRequest,
    CameraNodePreviewRequest,
    CameraNodePairRevokeRequest,
    CameraHealthDetailResponse,
    CameraHealthIncidentListResponse,
    CameraHealthListResponse,
    CameraHealthState,
    ClassifierReadinessReport,
    ClassifierManifestFileExportRequest,
    ClassifierManifestFileExportResponse,
    ClassifierTrainingManifestResponse,
    DatasetCoverageSummary,
    DatasetExport,
    DatasetExportCreate,
    DatasetExportDetail,
    DatasetExportManifest,
    DatasetQualitySummary,
    DashboardStreamRuntimeStatus,
    DashboardSummary,
    DemoDetectionRunCreate,
    DemoDetectionRunResult,
    DetectionProposal,
    DetectionProposalCreate,
    DetectionProposalDecisionCreate,
    DetectionProposalDecisionResult,
    DetectionRun,
    DetectionRunCreate,
    ExternalUrlWorkerDryRunResponse,
    ExternalUrlPreviewRequest,
    ExternalUrlPreviewResponse,
    ExternalUrlPreviewSaveRequest,
    ExternalUrlPreviewSaveResponse,
    FastReviewCorrectionCreate,
    FastReviewCorrectionResponse,
    FastReviewQueueNavigationRequest,
    FastReviewQueueNavigationResponse,
    FastReviewUndoRequest,
    FastReviewUndoResponse,
    LikelySpeciesOverviewResponse,
    LocalCameraFrameCaptureResponse,
    LiveCameraSessionDiagnosticsResponse,
    LiveCameraSessionStatusResponse,
    LivePreviewLeaseRequest,
    LivePreviewLeaseResponse,
    LivePreviewLeaseStatus,
    LivePreviewReleaseResponse,
    Event,
    EventDetail,
    FolderImportCreate,
    FolderImportEvidenceBatchCreateRequest,
    FolderImportEvidenceBatchCreateResponse,
    FolderImportEvidenceBatchDryRunRequest,
    FolderImportEvidenceBatchDryRunResponse,
    FolderImportPreview,
    FolderImportPreviewRequest,
    FolderImportResult,
    LocalDataStatus,
    LocalBackupLibraryResponse,
    LocalBackupRestorePlan,
    LocalBackupRestorePlanRequest,
    LocalBackupRestoreRequest,
    LocalBackupRestoreResponse,
    LocalBackupSummary,
    LocalBackupVerificationResponse,
    LiveMotionEvaluateRequest,
    LiveMotionEvaluateResponse,
    LiveMotionFrameSummary,
    LiveMotionMonitorSettingsRequest,
    LiveMotionMonitorStartRequest,
    LiveMotionReviewActivityResponse,
    MediaAsset,
    MediaImportResult,
    ModelAdapter,
    ModelReadinessSummary,
    ModelAdapterRunRequest,
    ModelAdapterRunResult,
    MockSpeciesSuggestionRequest,
    MotionCandidateResponse,
    MotionActivityAreaResponse,
    MotionCropBoxNormalizedResponse,
    MotionCropBoxPixelsResponse,
    MotionCropPlanResponse,
    MotionEvidenceAttachMediaRequest,
    MotionEvidenceBulkActionRequest,
    MotionEvidenceBulkActionResponse,
    MotionEvidenceCreateRequest,
    MotionEvidenceListResponse,
    MotionEvidencePromoteRequest,
    MotionEvidencePromoteResponse,
    MotionEvidenceResponse,
    MotionEvidenceStatus,
    MotionEvaluateFrameRequest,
    MotionEvaluateSavedMediaRequest,
    MotionEvaluateSavedMediaResponse,
    MotionEvaluateSequenceRequest,
    MotionEvaluateSequenceResponse,
    MotionExtractCandidatesRequest,
    MotionExtractCandidatesResponse,
    MotionFrameScoreResponse,
    MotionScoreResponse,
    MotionSuppressedZoneSummaryResponse,
    MotionZoneInput,
    ProductAlertListResponse,
    ProductAlertMarkVisibleReadRequest,
    ProductAlertUnreadResponse,
    ProductHealthBackupSummary,
    ProductHealthCameraSummary,
    ProductHealthObservationSummary,
    ProductHealthStatus,
    ProductInstanceIdentity,
    ReviewLabel,
    ReviewCorrectionCreate,
    ReviewCorrectionResult,
    ReviewLabelProvenanceReclassifyRequest,
    ReviewStatus,
    VisitEvidenceCurationRequest,
    VisitEvidenceCurationResponse,
    RefinedCropCreateRequest,
    RefinedCropResponse,
    VisitMergeCandidatesResponse,
    VisitMergePreview,
    VisitMergePreviewRequest,
    VisitMergeRequest,
    VisitMergeResponse,
    VisitReviewHistory,
    VisitReviewReopenCreate,
    VisitReviewReopenResponse,
    VisitReviewRevisionCreate,
    VisitReviewRevisionResponse,
    VisitSplitPreview,
    VisitSplitPreviewRequest,
    VisitSplitRequest,
    VisitSplitResponse,
    VisitZoneReassignmentRequest,
    VisitZoneReassignmentResponse,
    VisitIdentificationAssistantRequest,
    VisitIdentificationAssistantResponse,
    ReviewIdentificationRequest,
    ReviewIdentificationResponse,
    ReviewQueueBulkCorrectionRequest,
    ReviewQueueBulkCorrectionResponse,
    ReviewQueueItem,
    ReviewQueueSpeciesSuggestionBatchPrepareRequest,
    ReviewQueueSpeciesSuggestionBatchPrepareResponse,
    SetupState,
    SetupStateUpdate,
    SavedMediaBulkMotionEvidenceRequest,
    SavedMediaBulkMotionEvidenceResponse,
    SavedMediaFrameSummary,
    SavedMediaCleanupDryRunRequest,
    SavedMediaCleanupDryRunResponse,
    SavedMediaCleanupRequest,
    SavedMediaCleanupResponse,
    SavedMediaRetentionReportResponse,
    SavedPreviewMotionEvidenceRequest,
    SavedPreviewMotionEvidenceResponse,
    SampleDataRemovalRequest,
    SampleDataRemovalResponse,
    SpeciesSuggestionCreateRequest,
    SpeciesSuggestionListResponse,
    SpeciesSuggestionResponse,
    SpeciesSuggestionStatus,
    SpeciesSuggestionStatusUpdateRequest,
    SpeciesCandidatePack,
    SpeciesCandidatePackCloneRequest,
    SpeciesCandidatePackCreate,
    SpeciesCandidatePackUpdate,
    StreamSpeciesCandidatePackSelection,
    StreamSpeciesCandidatePackSelectionUpdate,
    SourceConnectionStatus,
    SourceConnectionStatusResponse,
    CameraSetupCompleteRequest,
    CameraSetupCompletionResponse,
    CameraSetupOptionsResponse,
    CameraSetupValidationRequest,
    CameraSetupValidationResponse,
    SourceFolderImportRequest,
    SourceFolderImportResponse,
    SourceMonitorStartRequest,
    SourceMonitorStatusResponse,
    CounterfactualConfidenceSummaryResponse,
    CounterfactualCoverageResponse,
    CounterfactualLedgerAccountingResponse,
    CounterfactualProposalOutcomeResponse,
    CounterfactualRawDetectionResponse,
    CounterfactualTrackGenerationResponse,
    CounterfactualWindowResponse,
    ObservationEngineStatusResponse,
    ObservationProviderCapabilitiesResponse,
    ObservationProviderHealthResponse,
    ObservationSessionCounts,
    ObservationSessionStatusResponse,
    OnvifDiscoverProfilesRequest,
    OnvifDiscoverProfilesResponse,
    OnvifDiscoveredProfile,
    OnvifRecordProfileRequest,
    OnvifRecordProfileResponse,
    PlaceActivityReportRequest,
    PlaceActivityReportResponse,
    SourceFolderImportPreviewRequest,
    SourceFolderImportPreviewResponse,
    SourceProviderConfiguration,
    SourceProviderConfigurationUpdate,
    SourceProviderDefinition,
    SourceSetupReviewResponse,
    SourceStatus,
    Stream,
    StorageCleanupExecuteRequest,
    StorageCleanupHistoryResponse,
    StorageCleanupPreviewResponse,
    StorageCleanupPurgeRequest,
    StorageCleanupRestoreRequest,
    StorageCleanupResult,
    StorageRetentionSettings,
    StorageRetentionSettingsUpdate,
    StorageSummary,
    StreamMonitoringMutationResponse,
    StreamMonitoringMode,
    StreamMonitoringPolicyResponse,
    StreamMonitoringPolicyUpdate,
    StreamMonitoringRetryRequest,
    StreamMonitoringStatusListResponse,
    StreamPlaybackStatus,
    StreamPlaybackStatusResponse,
    StreamPlaybackStatusValue,
    StreamRuntimeStatusResponse,
    StreamVisitSummary,
    TaxonomyLabel,
    Visit,
    VisitDetail,
    VisitOrganizationState,
    VisitOrganizationUpdate,
    VisitOrganizationBulkRequest,
    VisitOrganizationBulkResponse,
    VisitCollectionArchiveRequest,
    VisitCollectionBulkRequest,
    VisitCollectionBulkResponse,
    VisitCollectionCreate,
    VisitCollectionMembershipRequest,
    VisitCollectionMembershipResponse,
    VisitCollectionSummary,
    VisitCollectionUpdate,
    VisitCollectionsForVisitResponse,
    VisitTagArchiveRequest,
    VisitTagBulkRequest,
    VisitTagBulkResponse,
    VisitTagCreate,
    VisitTagMembershipRequest,
    VisitTagMembershipResponse,
    VisitTagSummary,
    VisitTagUpdate,
    VisitTagsForVisitResponse,
    WebhookMotionEvidenceRequest,
    WebhookMotionEvidenceResponse,
    WebhookPayloadValidationRequest,
    WebhookPayloadValidationResponse,
    WorkerStatusResponse,
    YardMapBackgroundDelete,
    YardMapBlankCreate,
    YardMapPlacementDelete,
    YardMapResponse,
    YardMapSettingsUpdate,
    YardMapStreamPlacementUpdate,
    YardMapZonePlacementUpdate,
    WildlifeInsightsRequest,
    WildlifeInsightsSummary,
    ZoneInsightsRequest,
    ZoneInsightsSummary,
    WildlifeJournalHistoryRequest,
    WildlifeJournalHistoryResponse,
    WildlifeJournalGalleryOrder,
    WildlifeJournalOrder,
    WildlifeJournalOverviewRequest,
    WildlifeJournalOverviewResponse,
    WildlifeJournalRangePreset,
    WindowsCameraControlsResponse,
    WindowsCameraDiscoveryResponse,
    Zone,
    ZoneActivitySensitivity,
    ZoneCreate,
    ZoneMonitoringPolicy,
    ZoneMonitoringPolicyUpdate,
    ZoneMutationResult,
    ZoneType,
    ZoneUpdate,
)
from mockingbird.motion import (
    MotionCandidate,
    MotionFrameScore,
    MotionScore,
    MotionZone,
    extract_motion_candidates,
    score_frame_motion,
    score_zone_motion,
)
from mockingbird.motion.activity_crop import (
    ActivityCropPlan,
    ChangedActivityBounds,
    CropBoxNormalized,
    locate_changed_activity_bounds,
    plan_activity_crop,
)
from mockingbird.motion.activity_session import (
    DEFAULT_QUIET_PERIOD_SECONDS,
    ExistingActivityReference,
    recommend_activity_session,
)
from mockingbird.motion.high_resolution_evidence import (
    CaptureProfileGeometry,
    crop_jpeg,
    padded_box,
    resolve_alignment,
)
from mockingbird.motion.local_activity_diagnostic import (
    activity_diagnostic_export_from_capture,
)
from mockingbird.motion.object_tracking import (
    LiveObjectDetectorManager,
    ObjectDetection,
    ObjectDetectorSnapshot,
    ObjectTrack,
    ObjectTrackTrigger,
    detector_provenance,
)
from mockingbird.motion.tracked_activity import (
    AnalysisPreset,
    FrameTelemetry,
    MotionRegion,
    TrackedActivityResult,
    TrackedOutdoorActivityDetectorManager,
    TrackTrigger,
    TrackedZone,
)
from mockingbird.monitoring import (
    DurableMonitoringCandidate,
    DurableMonitoringSupervisor,
    ManagedCameraStatus,
    MonitorMotionResult,
    MonitorSnapshotResult,
    SourceMonitorManager,
    SourceMonitorOptions,
    SourceMonitorState,
)
from mockingbird.observation import (
    ObservationEngineRegistry,
    SnapshotObservationProvider,
    unified_status,
)
from mockingbird.observation.acceptance_recorder import (
    ACCEPTANCE_RECORDING_DIR_ENV,
    acceptance_recorder_config_from_env,
)
from mockingbird.observation.counterfactual_lineage import classify_rejection_attribution
from mockingbird.observation.engine_runtime import (
    ObservationEngineSessionManager,
    ObservationEngineSessionStatus,
)
from mockingbird.playback import (
    live_camera_session,
    live_frame_cache,
    live_preview_leases,
    local_camera_bridge,
    rtsp_bridge,
    windows_camera_bridge,
)
from mockingbird.repository.product_repository import (
    CameraConfigurationConflictError,
    CameraNodePendingSetup,
    FastReviewConflictError,
    MonitoringOperationConflictError,
    ProductRepository,
    ReviewProvenanceConflictError,
    ReviewRevisionConflictError,
    VisitCurationConflictError,
    StreamLivePlaybackConfig,
)
from mockingbird.review_provenance import ReviewProvenanceError
from mockingbird.sampler import (
    SamplerConfig,
    SamplerContext,
    SamplerResult,
    SamplerZone,
    create_motion_evidence_from_sampler_result,
    evaluate_sampled_frame_sequence,
)
from mockingbird.sampler.saved_media_frames import (
    SavedMediaFrame,
    SavedMediaFrameDecodeError,
    load_image_frame_plane_bytes,
    load_saved_image_frame_plane,
)
from mockingbird.source_providers import external_url_preview
from mockingbird.source_providers import onvif_client
from mockingbird.source_providers.camera_node import (
    CAMERA_NODE_RUNTIME_FAILURE_CODES,
    CameraNodeCaptureProfile as NodeCaptureProfile,
    CameraNodeClient,
    CameraNodeClientError,
    CameraNodePairing,
)
from mockingbird.species.automatic_identification import (
    AutomaticReviewIdentificationAssist,
)
from mockingbird.storage.backup import (
    BackupSummaryData,
    BackupVerificationData,
    RestorePlanData,
    LocalBackupConflictError,
    LocalBackupError,
    LocalBackupManager,
    LocalBackupNotFoundError,
    LocalBackupRestoreError,
    LocalBackupUnsupportedError,
    LocalBackupValidationError,
)
from mockingbird.runtime_state import (
    current_log_path,
    current_runtime_home,
    mark_clean_shutdown,
    previous_shutdown_was_clean,
    resolve_build_identity,
    resolve_instance_id,
)
from mockingbird.storage.database import (
    LOW_DISK_FREE_BYTES_THRESHOLD,
    LOW_DISK_FREE_RATIO_THRESHOLD,
    create_database_engine,
)
from mockingbird.storage.retention_service import LocalStorageRetentionService
from mockingbird.web_app import frontend_response


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    """Validate local data, restore explicit monitoring intent, and stop safely."""

    global _live_object_detector_manager
    repository = get_repository()
    get_durable_monitoring_supervisor().start()
    if repository.storage_retention_settings().automatic_cleanup_enabled:
        get_local_storage_retention_service().start()
    try:
        yield
    finally:
        detector_drained = False

        def drain_live_detector() -> None:
            nonlocal detector_drained
            if _live_object_detector_manager is not None and not detector_drained:
                _live_object_detector_manager.shutdown()
                detector_drained = True

        if _local_storage_retention_service is not None:
            _local_storage_retention_service.shutdown()
        if _durable_monitoring_supervisor is not None:
            _durable_monitoring_supervisor.shutdown(
                reason="api_shutdown", before_persist_stop=drain_live_detector
            )
        else:
            drain_live_detector()
        if _source_monitor_manager is not None:
            _source_monitor_manager.cancel_all()
        if _live_preview_lease_manager is not None:
            _live_preview_lease_manager.shutdown()
        if _live_camera_session_manager is not None:
            _live_camera_session_manager.stop_all(reason="api_shutdown")
        if detector_drained:
            _live_object_detector_manager = None
        if _automatic_review_identification_assist is not None:
            _automatic_review_identification_assist.shutdown()
        # Recorded last: a process that dies before reaching this line still
        # correctly reports "did not shut down cleanly" on its next launch.
        mark_clean_shutdown()


app = FastAPI(
    title="MockingBird API",
    version="0.1.0",
    description=(
        "Local-first outdoor video intelligence centered on streams, zones, "
        "events, visits, review, corrections, exports, and analytics."
    ),
    lifespan=_app_lifespan,
)

# Local Vite dev origins let the stream-first frontend use the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _patch_testclient_for_pytest() -> None:
    if "pytest" not in sys.modules:
        return

    try:
        import httpx
        from starlette.testclient import TestClient as StarletteTestClient
    except ImportError:
        return

    if getattr(StarletteTestClient, "_mockingbird_asgi_transport_patch", False):
        return

    def __init__(
        self,
        app,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: str = "asyncio",
        backend_options: dict | None = None,
        cookies=None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        client: tuple[str, int] = ("testclient", 50000),
    ) -> None:
        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path
        self.follow_redirects = follow_redirects
        self.cookies = cookies
        self.client = client
        self.headers = dict(headers or {})
        self.headers.setdefault("user-agent", "testclient")

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(
                app=self.app,
                raise_app_exceptions=self.raise_server_exceptions,
                root_path=self.root_path,
                client=self.client,
            )
            async with httpx.AsyncClient(
                transport=transport,
                base_url=self.base_url,
                cookies=self.cookies,
                headers=self.headers,
                follow_redirects=self.follow_redirects,
            ) as api_client:
                return await api_client.request(method, url, **kwargs)

        return asyncio.run(send())

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    # Test-only compatibility for the local Starlette TestClient lifespan hang.
    StarletteTestClient.__init__ = __init__
    StarletteTestClient.request = request
    StarletteTestClient.get = get
    StarletteTestClient.post = post
    StarletteTestClient.patch = patch
    StarletteTestClient.__enter__ = __enter__
    StarletteTestClient.__exit__ = __exit__
    StarletteTestClient._mockingbird_asgi_transport_patch = True


_patch_testclient_for_pytest()

_repository: ProductRepository | None = None
_source_monitor_manager: SnapshotObservationProvider | None = None
_live_camera_session_manager: live_camera_session.LiveCameraSessionManager | None = None
_observation_engine_session_manager: ObservationEngineSessionManager | None = None
_live_preview_lease_manager: live_preview_leases.LivePreviewLeaseManager | None = None
_durable_monitoring_supervisor: DurableMonitoringSupervisor | None = None
_local_storage_retention_service: LocalStorageRetentionService | None = None
_camera_node_client: CameraNodeClient | None = None
_automatic_review_identification_assist: AutomaticReviewIdentificationAssist | None = (
    None
)
_tracked_activity_detector_manager: TrackedOutdoorActivityDetectorManager | None = None
_CAMERA_NODE_PAIRING_REFRESH_ATTEMPTS = 12
_CAMERA_NODE_PAIRING_REFRESH_INTERVAL_SECONDS = 1.0
_live_object_detector_manager: LiveObjectDetectorManager | None = None
_backup_operation_lock = threading.Lock()
_repository_access_lock = threading.RLock()
# `asyncio.create_task`'s own docs warn the event loop only holds a *weak*
# reference to a task -- without a strong reference elsewhere, a detached
# background task (currently only `_refresh_camera_node_pairing_profiles`,
# fired-and-forgotten by `pair_camera_node`) can be garbage-collected
# mid-execution. Tracking it here also lets `drain_background_tasks` (Test
# / Development Repository Isolation v1, Part 6) give a test's own teardown
# a deterministic way to wait for it to finish *before* an isolated
# repository is torn down, instead of racing it: this exact task calls
# `get_repository()` again after its first `await`, so a test that resets
# the repository singleton while it is still sleeping would otherwise hand
# it the unconfigured default the moment it wakes up.
_pending_background_tasks: set[asyncio.Task] = set()


def _track_background_task(task: asyncio.Task) -> None:
    _pending_background_tasks.add(task)
    task.add_done_callback(_pending_background_tasks.discard)


async def drain_background_tasks() -> None:
    """Wait for every currently-tracked detached background task to finish.

    Deliberately does *not* pass `return_exceptions=True`: a genuine
    failure inside a drained task (for example this exact isolation
    guard's own `UnsafeDefaultStorageAccessError`, if a caller drains too
    late) must still surface loudly, never be silently absorbed -- the same
    fail-closed principle the guard itself exists for.

    Test-only concern in practice (see `tests/conftest.py`): production
    shutdown already stops durable/worker lifecycles explicitly through
    `_stop_runtime_activity`, and this process only ever creates the one
    short-lived, bounded task named above. Snapshotting before awaiting is
    enough for that -- it does not need to loop until the set is empty.
    """

    pending = tuple(_pending_background_tasks)
    if pending:
        await asyncio.gather(*pending)


def get_repository() -> ProductRepository:
    global _repository
    # Restore holds this lock across the live file swap so ordinary page loads
    # cannot initialize a second repository against an in-between filesystem.
    with _repository_access_lock:
        if _repository is None:
            _repository = ProductRepository()
        return _repository


def get_camera_node_client() -> CameraNodeClient:
    global _camera_node_client
    if _camera_node_client is None:
        _camera_node_client = CameraNodeClient()
    return _camera_node_client


async def _refresh_camera_node_pairing_profiles(
    *,
    pairing_token: str,
    pairing: CameraNodePairing,
) -> None:
    """Boundedly refresh a just-paired Node while its local warm proof completes.

    This work is part of the explicit one-time pairing action.  It does not
    start a camera from a status/configuration read or create product
    records; it updates only the transient advertised-camera list on the
    already-durable pending setup record (see
    docs/camera-node-pairing-persistence-design.md).
    """

    client = get_camera_node_client()
    repository = get_repository()
    for attempt in range(_CAMERA_NODE_PAIRING_REFRESH_ATTEMPTS):
        try:
            cameras = client.cameras(
                base_address=pairing.base_address,
                credential=pairing.credential,
            )
        except CameraNodeClientError:
            return
        if not repository.refresh_camera_node_pending_setup_cameras(pairing_token, cameras):
            return
        if any(_camera_node_has_warm_profile_pair(camera) for camera in cameras):
            return
        if attempt + 1 < _CAMERA_NODE_PAIRING_REFRESH_ATTEMPTS:
            await asyncio.sleep(_CAMERA_NODE_PAIRING_REFRESH_INTERVAL_SECONDS)


def _camera_node_profile_selection(camera: Any) -> tuple[NodeCaptureProfile | None, NodeCaptureProfile | None]:
    """Resolve safe Node-owned monitoring/evidence profiles without device details."""

    profiles = [
        profile
        for profile in getattr(camera, "capture_profiles", ())
        if profile.jpeg_supported
    ]
    monitoring_candidates = [
        profile for profile in profiles if profile.supports_monitoring
    ]
    warm_evidence_candidates = sorted(
        (
            profile
            for profile in profiles
            if profile.supports_evidence
            and profile.capture_class == "warm_concurrent"
            and profile.same_fov
            and profile.geometry_group is not None
        ),
        key=lambda profile: profile.width * profile.height,
        reverse=True,
    )
    for evidence in warm_evidence_candidates:
        aligned_monitoring = [
            profile
            for profile in monitoring_candidates
            if profile.geometry_group == evidence.geometry_group
            and profile.same_fov
        ]
        if aligned_monitoring:
            return max(
                aligned_monitoring,
                key=lambda profile: profile.width * profile.height,
            ), evidence
    monitoring = max(
        (
            profile
            for profile in monitoring_candidates
            if profile.width <= 1920 and profile.height <= 1080
        ),
        key=lambda profile: profile.width * profile.height,
        default=(
            min(
                monitoring_candidates,
                key=lambda profile: profile.width * profile.height,
            )
            if monitoring_candidates
            else None
        ),
    )
    evidence_candidates = [
        profile for profile in profiles if profile.supports_evidence
    ]
    aligned = [
        profile
        for profile in evidence_candidates
        if monitoring is not None
        and profile.geometry_group is not None
        and profile.geometry_group == monitoring.geometry_group
        and profile.same_fov
    ]
    # An unaligned still can still be preserved as full-frame evidence; the
    # crop path will explicitly decline to map a track onto it.
    preferred = [
        profile
        for profile in (aligned or evidence_candidates)
        if profile.capture_class == "warm_concurrent"
    ]
    evidence = max(
        preferred or aligned or evidence_candidates,
        key=lambda profile: profile.width * profile.height,
        default=None,
    )
    return monitoring, evidence


def _camera_node_has_warm_profile_pair(camera: Any) -> bool:
    monitoring, evidence = _camera_node_profile_selection(camera)
    return bool(
        monitoring is not None
        and evidence is not None
        and monitoring.capture_class == "warm_concurrent"
        and evidence.capture_class == "warm_concurrent"
    )


_HIGH_RESOLUTION_CAPTURE_TRANSIENT_FAILURES = frozenset(
    {
        "node_camera_unavailable",
        "node_snapshot_timeout",
        "node_unavailable",
    }
)
_EXPECTED_HIGH_RESOLUTION_EVIDENCE_DIMENSIONS = (4624, 3472)


def _capture_profile_geometry(profile: NodeCaptureProfile) -> CaptureProfileGeometry:
    return CaptureProfileGeometry(
        profile_id=profile.profile_id,
        width=profile.width,
        height=profile.height,
        geometry_group=profile.geometry_group,
        orientation=profile.orientation,
        mirrored=profile.mirrored,
        same_fov=profile.same_fov,
    )


def _high_resolution_capture_claim_profile_lineage(
    configuration: StreamLivePlaybackConfig | None,
) -> dict[str, Any]:
    """Freeze the opaque Node profile geometry immediately before a claim."""

    if (
        configuration is None
        or configuration.provider_key != "camera_node"
        or configuration.live_stream_type != "camera_node"
        or not configuration.camera_node_base_address
        or not configuration.camera_node_credential
        or not configuration.camera_node_camera_id
        or not configuration.camera_node_monitoring_profile_id
        or not configuration.camera_node_evidence_profile_id
    ):
        return {}
    try:
        camera = next(
            (
                item
                for item in get_camera_node_client().cameras(
                    base_address=configuration.camera_node_base_address,
                    credential=configuration.camera_node_credential,
                )
                if item.camera_id == configuration.camera_node_camera_id
                and item.status == "available"
                and item.snapshot_supported
            ),
            None,
        )
    except CameraNodeClientError as error:
        return {"capture_profile_lookup_failure_code": str(error)}
    if camera is None:
        return {"capture_profile_lookup_failure_code": "node_camera_unavailable"}
    profiles_by_id = {profile.profile_id: profile for profile in camera.capture_profiles}
    monitoring = profiles_by_id.get(configuration.camera_node_monitoring_profile_id)
    evidence = profiles_by_id.get(configuration.camera_node_evidence_profile_id)
    if (
        monitoring is None
        or evidence is None
        or not monitoring.supports_monitoring
        or not evidence.supports_evidence
    ):
        return {
            "capture_profile_lookup_failure_code": "node_capture_profile_unavailable"
        }
    return {
        "monitoring_profile_id": monitoring.profile_id,
        "evidence_profile_id": evidence.profile_id,
        "monitoring_geometry_group_id": monitoring.geometry_group,
        "alignment_group_id": evidence.geometry_group,
        "evidence_profile_width": evidence.width,
        "evidence_profile_height": evidence.height,
    }


def _capture_high_resolution_activity_evidence(
    *,
    configuration: StreamLivePlaybackConfig | None,
    region: MotionRegion | None,
    trigger_track_id: str | None,
    trigger_at: datetime | None,
    capture_claim: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Request one Node-owned still after a coherent track has qualified.

    This remains an in-memory activity artifact until the existing bounded
    review handoff creates a Visit.  A Node may receive only its selected,
    advertised opaque profile ID; callers cannot choose dimensions or driver
    settings.
    """

    if (
        configuration is None
        or configuration.provider_key != "camera_node"
        or configuration.live_stream_type != "camera_node"
        or not configuration.camera_node_base_address
        or not configuration.camera_node_credential
        or not configuration.camera_node_camera_id
        or not configuration.camera_node_monitoring_profile_id
        or not configuration.camera_node_evidence_profile_id
        or region is None
    ):
        return None

    requested_at = (
        _live_activity_datetime(capture_claim.get("request_timestamp"))
        if capture_claim is not None
        else None
    ) or datetime.now(UTC)
    track_box = (region.left, region.top, region.right, region.bottom)
    capture_context: dict[str, Any] = {
        **dict(capture_claim or {}),
        "monitoring_profile_id": configuration.camera_node_monitoring_profile_id,
        "evidence_profile_id": configuration.camera_node_evidence_profile_id,
        "trigger_id": (
            f"{region.zone_id}:{capture_claim['track_generation_id']}"
            if capture_claim is not None and capture_claim.get("track_generation_id")
            else f"{region.zone_id}:{trigger_track_id}"
            if trigger_track_id
            else region.zone_id
        ),
        "trigger_started_at": trigger_at,
        "capture_requested_at": requested_at,
        "normalized_track_box": list(track_box),
    }
    client = get_camera_node_client()
    try:
        camera = next(
            (
                item
                for item in client.cameras(
                    base_address=configuration.camera_node_base_address,
                    credential=configuration.camera_node_credential,
                )
                if item.camera_id == configuration.camera_node_camera_id
                and item.status == "available"
                and item.snapshot_supported
            ),
            None,
        )
    except CameraNodeClientError as error:
        return {
            **capture_context,
            "alignment_status": "not_captured",
            "capture_failure_code": str(error),
        }
    if camera is None:
        return {
            **capture_context,
            "alignment_status": "not_captured",
            "capture_failure_code": "node_camera_unavailable",
        }

    profiles_by_id = {profile.profile_id: profile for profile in camera.capture_profiles}
    monitoring = profiles_by_id.get(configuration.camera_node_monitoring_profile_id)
    evidence = profiles_by_id.get(configuration.camera_node_evidence_profile_id)
    if (
        monitoring is None
        or evidence is None
        or not monitoring.supports_monitoring
        or not evidence.supports_evidence
    ):
        return {
            **capture_context,
            "alignment_status": "not_captured",
            "capture_failure_code": "node_capture_profile_unavailable",
        }

    if capture_claim is not None and (
        capture_claim.get("monitoring_profile_id") != monitoring.profile_id
        or capture_claim.get("evidence_profile_id") != evidence.profile_id
        or capture_claim.get("monitoring_geometry_group_id")
        != monitoring.geometry_group
        or capture_claim.get("alignment_group_id") != evidence.geometry_group
    ):
        return {
            **capture_context,
            "alignment_status": "not_captured",
            "capture_failure_code": "capture_profile_geometry_changed",
        }

    capture = None
    failure_code: str | None = None
    for attempt in range(2):
        try:
            capture = client.capture(
                base_address=configuration.camera_node_base_address,
                credential=configuration.camera_node_credential,
                camera_id=camera.camera_id,
                profile=evidence,
            )
            break
        except CameraNodeClientError as error:
            failure_code = str(error)
            if attempt or failure_code not in _HIGH_RESOLUTION_CAPTURE_TRANSIENT_FAILURES:
                break
    completed_at = datetime.now(UTC)
    capture_latency_ms = max(
        0,
        round((completed_at - requested_at).total_seconds() * 1000),
    )
    if capture is None:
        return {
            **capture_context,
            "capture_latency_ms": capture_latency_ms,
            "alignment_status": "not_captured",
            "capture_failure_code": failure_code or "node_unavailable",
        }

    if (capture.width, capture.height) != _EXPECTED_HIGH_RESOLUTION_EVIDENCE_DIMENSIONS:
        return {
            **capture_context,
            "capture_latency_ms": capture_latency_ms,
            "alignment_status": "not_captured",
            "capture_failure_code": "unexpected_evidence_dimensions",
            "full_width": capture.width,
            "full_height": capture.height,
        }

    captured_at = capture.captured_at or completed_at
    decision = resolve_alignment(
        _capture_profile_geometry(monitoring),
        _capture_profile_geometry(evidence),
    )
    padded_track_box = None
    crop = None
    alignment_status = decision.status
    alignment_failure_code = decision.failure_code
    transform_id = decision.transform.transform_id if decision.transform else None
    if decision.transform is not None:
        mapped_track_box = decision.transform.map_box(track_box)
        padded_track_box = (
            padded_box(mapped_track_box, padding_ratio=0.35)
            if mapped_track_box is not None
            else None
        )
        if padded_track_box is None:
            alignment_status = "full_only"
            alignment_failure_code = "track_geometry_invalid"
        else:
            crop = crop_jpeg(capture.image, padded_track_box)
            if crop is None:
                alignment_status = "full_only"
                alignment_failure_code = "crop_derivation_failed"
    return {
        **capture_context,
        "capture_profile_id": capture.profile_id,
        "alignment_group_id": (
            capture_claim.get("alignment_group_id")
            if capture_claim is not None
            else evidence.geometry_group
        ),
        "monitoring_recovery": capture.monitoring_recovery,
        "full_image": capture.image,
        "full_width": capture.width,
        "full_height": capture.height,
        "crop_image": crop.image if crop is not None else None,
        "crop_width": crop.width if crop is not None else None,
        "crop_height": crop.height if crop is not None else None,
        "normalized_padded_crop_box": (
            list(crop.normalized_crop_box) if crop is not None else None
        ),
        "geometry_transform_id": transform_id,
        "alignment_status": alignment_status,
        "alignment_failure_code": alignment_failure_code,
        "captured_at": captured_at,
        "capture_latency_ms": capture_latency_ms,
        "track_to_capture_delay_ms": (
            max(0, round((requested_at - trigger_at).total_seconds() * 1000))
            if trigger_at is not None
            else None
        ),
    }


def _camera_node_prepared_config(
    *,
    provider_key: str,
    config: dict[str, str | None],
    pairing_token: str | None,
    verify_camera: bool = False,
) -> dict[str, str | None]:
    """Materialize a server-held pairing only for the bounded persistence call.

    Credentials never travel back to the browser and are never included in an
    API response. The browser can select only an opaque advertised camera ID.
    """

    if provider_key != "camera_node":
        return config
    camera_id = (config.get("node_camera_id") or "").strip()
    if not pairing_token or not camera_id:
        raise ValueError("camera_node_pairing_required")
    repository = get_repository()
    pairing = repository.resolve_camera_node_pending_pairing(pairing_token, camera_id=camera_id)
    if pairing is None:
        raise ValueError("camera_node_pairing_expired")
    selected_camera = next(
        (camera for camera in pairing.cameras if camera.camera_id == camera_id),
        None,
    )
    if verify_camera:
        try:
            advertised = get_camera_node_client().cameras(
                base_address=pairing.base_address,
                credential=pairing.credential,
            )
        except CameraNodeClientError as error:
            if str(error) == "authentication_rejected":
                # The Node itself rejected our stored credential -- a genuine
                # revocation, not a transient network failure. Mark the
                # durable pending setup so a resumed wizard shows "pairing
                # needs to be renewed" instead of silently retrying forever.
                repository.mark_camera_node_pending_setup_needs_renewal(pairing_token)
            raise
        selected_camera = next(
            (
                camera
                for camera in advertised
                if camera.camera_id == camera_id
                and camera.status == "available"
                and camera.snapshot_supported
            ),
            None,
        )
        if selected_camera is None:
            raise ValueError("camera_node_camera_unavailable")
    monitoring_profile, evidence_profile = _camera_node_profile_selection(
        selected_camera
    ) if selected_camera is not None else (None, None)
    return {
        "node_base_address": pairing.base_address,
        "node_credential": pairing.credential,
        "node_camera_id": camera_id,
        "node_id": pairing.node_id,
        "node_display_name": pairing.display_name,
        "node_api_version": pairing.api_version,
        "node_capability_fingerprint": pairing.capability_fingerprint,
        "node_pairing_state": "paired",
        "node_monitoring_profile_id": (
            monitoring_profile.profile_id if monitoring_profile is not None else None
        ),
        "node_evidence_profile_id": (
            evidence_profile.profile_id if evidence_profile is not None else None
        ),
    }


def _camera_node_prepared_edit_payload(
    payload: CameraConfigurationImpactPreviewRequest | CameraConfigurationApplyRequest,
    *,
    verify_camera: bool = False,
) -> CameraConfigurationImpactPreviewRequest | CameraConfigurationApplyRequest:
    if payload.provider_key != "camera_node" or not payload.node_pairing_token:
        return payload
    configured = _camera_node_prepared_config(
        provider_key=payload.provider_key,
        config=payload.config,
        pairing_token=payload.node_pairing_token,
        verify_camera=verify_camera,
    )
    for key in {"node_monitoring_profile_id", "node_evidence_profile_id"}:
        if not configured.get(key):
            configured.pop(key, None)
    secret_actions = dict(payload.secret_actions)
    for key in {
        "node_base_address",
        "node_credential",
        "node_camera_id",
        "node_id",
        "node_capability_fingerprint",
    }:
        secret_actions[key] = CameraConfigurationSecretAction.replace
    for key in {"node_monitoring_profile_id", "node_evidence_profile_id"}:
        secret_actions[key] = (
            CameraConfigurationSecretAction.replace
            if configured.get(key)
            else CameraConfigurationSecretAction.remove
        )
    return payload.model_copy(update={"config": configured, "secret_actions": secret_actions})


def configure_repository(repository: ProductRepository | None) -> None:
    global _repository
    with _repository_access_lock:
        previous_repository = _repository
        _stop_runtime_activity(reason="repository_reconfigured")
        _repository = repository
        if previous_repository is not None and previous_repository is not repository:
            previous_repository.close()


def _stop_runtime_activity(*, reason: str) -> None:
    global _automatic_review_identification_assist
    global _durable_monitoring_supervisor, _local_storage_retention_service
    global _source_monitor_manager, _live_camera_session_manager, _live_preview_lease_manager
    global _live_object_detector_manager, _tracked_activity_detector_manager
    global _observation_engine_session_manager
    detector_drained = False

    def drain_live_detector() -> None:
        nonlocal detector_drained
        if _live_object_detector_manager is not None and not detector_drained:
            _live_object_detector_manager.shutdown()
            detector_drained = True

    if _durable_monitoring_supervisor is not None:
        _durable_monitoring_supervisor.shutdown(
            reason=reason, before_persist_stop=drain_live_detector
        )
        _durable_monitoring_supervisor = None
    else:
        drain_live_detector()
    if _local_storage_retention_service is not None:
        _local_storage_retention_service.shutdown()
        _local_storage_retention_service = None
    if _source_monitor_manager is not None:
        _source_monitor_manager.cancel_all()
        _source_monitor_manager = None
    if _live_preview_lease_manager is not None:
        _live_preview_lease_manager.shutdown()
        _live_preview_lease_manager = None
    if _live_camera_session_manager is not None:
        _live_camera_session_manager.stop_all(reason=reason)
        _live_camera_session_manager = None
    if _observation_engine_session_manager is not None:
        _observation_engine_session_manager.stop_all(reason=reason)
        _observation_engine_session_manager = None
    if _live_object_detector_manager is not None:
        # The manager was drained before durable stop persistence; release its
        # owner reference only after the rest of process-owned cleanup finishes.
        _live_object_detector_manager = None
    if _automatic_review_identification_assist is not None:
        _automatic_review_identification_assist.shutdown()
        _automatic_review_identification_assist = None
    _tracked_activity_detector_manager = None


def _local_backup_manager(
    repository: ProductRepository | None = None,
) -> LocalBackupManager:
    active_repository = repository or get_repository()
    return LocalBackupManager(
        db_url=active_repository.db_url,
        media_root=active_repository.media_root,
    )


def _local_backup_summary(data: BackupSummaryData) -> LocalBackupSummary:
    # Filesystem paths stay internal; the Local Data UI only needs artifact facts.
    return LocalBackupSummary(
        id=data.id,
        created_at=data.created_at,
        kind=data.kind,
        database_schema_version=data.database_schema_version,
        database_size_bytes=data.database_size_bytes,
        media_file_count=data.media_file_count,
        media_size_bytes=data.media_size_bytes,
        archive_size_bytes=data.archive_size_bytes,
        verification_status=data.verification_status,
        restore_compatible=data.restore_compatible,
    )


def _local_backup_verification_response(
    verification: BackupVerificationData,
    *,
    message: str,
) -> LocalBackupVerificationResponse:
    return LocalBackupVerificationResponse(
        backup=_local_backup_summary(verification.backup),
        checked_at=verification.checked_at,
        message=message,
    )


def _local_backup_restore_plan(
    data: RestorePlanData,
    *,
    dry_run: bool | None = None,
    confirmed: bool | None = None,
) -> LocalBackupRestorePlan:
    def safe_layout(path: str) -> dict[str, object]:
        windows = bool(len(path) >= 2 and path[1] == ":") or "\\" in path
        normalized = path.replace("\\", "/").rstrip("/")
        return {
            "platform": "windows" if windows else "posix",
            "absolute": (
                bool(len(path) >= 3 and path[1] == ":" and path[2] in {"\\", "/"})
                if windows
                else Path(path).is_absolute()
            ),
            "leaf_name": normalized.rsplit("/", 1)[-1],
        }

    return LocalBackupRestorePlan(
        database_schema_version=data.database_schema_version,
        source_database_layout=safe_layout(data.source_database_path),
        source_media_layout=safe_layout(data.source_media_root),
        target_database_layout=safe_layout(data.target_database_path),
        target_media_layout=safe_layout(data.target_media_root),
        managed_database_reference_count=data.managed_database_reference_count,
        media_archive_entry_count=data.media_archive_entry_count,
        external_paths_preserved=list(data.external_paths_preserved),
        warnings=list(data.warnings),
        unsafe_paths=list(data.unsafe_paths),
        collisions=list(data.collisions),
        expected_entity_counts=dict(data.expected_entity_counts),
        rebind_managed_storage=data.rebind_managed_storage,
        dry_run=data.dry_run if dry_run is None else dry_run,
        confirmed=data.confirmed if confirmed is None else confirmed,
        restore_allowed=data.restore_allowed,
    )


def _local_backup_http_error(error: LocalBackupError) -> HTTPException:
    code = str(error)
    if isinstance(error, LocalBackupNotFoundError):
        return HTTPException(
            status_code=404, detail="That local backup could not be found."
        )
    if isinstance(error, LocalBackupUnsupportedError):
        return HTTPException(
            status_code=409,
            detail="Backup is unavailable for the configured local storage layout.",
        )
    if isinstance(error, LocalBackupValidationError):
        return HTTPException(
            status_code=400,
            detail="Backup verification failed. No product data was changed.",
        )
    if isinstance(error, LocalBackupConflictError):
        if code == "backup_storage_layout_mismatch":
            return HTTPException(
                status_code=409,
                detail="This backup was made for a different local storage layout and cannot be restored here.",
            )
        return HTTPException(
            status_code=409,
            detail="A different backup with this identity is already in the local library.",
        )
    if isinstance(error, LocalBackupRestoreError):
        return HTTPException(
            status_code=500,
            detail="Restore could not finish safely. MockingBird attempted to preserve the previous local data.",
        )
    return HTTPException(
        status_code=500, detail="The local backup operation could not be completed."
    )


def _open_product_repository(
    *,
    db_url: str,
    media_root: Path,
    classifier_manifest_export_root: Path,
) -> ProductRepository:
    engine = create_database_engine(db_url)
    try:
        return ProductRepository(
            db_url=db_url,
            engine=engine,
            media_root=media_root,
            classifier_manifest_export_root=classifier_manifest_export_root,
        )
    except Exception:
        engine.dispose()
        raise


def get_source_monitor_manager() -> SnapshotObservationProvider:
    global _source_monitor_manager
    if _source_monitor_manager is None:
        _source_monitor_manager = SnapshotObservationProvider(
            SourceMonitorManager(
                capture_snapshot=_monitor_capture_snapshot,
                list_saved_images=_monitor_saved_image_ids,
                evaluate_saved_media=_monitor_evaluate_saved_media,
            )
        )
    return _source_monitor_manager


def get_observation_engine_registry() -> ObservationEngineRegistry:
    """Expose the active compatibility provider without starting monitoring."""

    return ObservationEngineRegistry([get_source_monitor_manager()])


def get_live_camera_session_manager() -> live_camera_session.LiveCameraSessionManager:
    global _live_camera_session_manager
    if _live_camera_session_manager is None:
        _live_camera_session_manager = live_camera_session.LiveCameraSessionManager()
    return _live_camera_session_manager


def get_observation_engine_session_manager() -> ObservationEngineSessionManager:
    """The app-owned Observation Engine lifecycle (Product requirement 1).

    Each background session opens its own dedicated `ProductRepository`
    (matching the resolved database/media root `get_repository()` already
    uses) rather than sharing the app's own instance, so a session can be
    closed independently on stop without ever touching the shared
    repository other requests depend on."""

    global _observation_engine_session_manager
    if _observation_engine_session_manager is None:
        # Independent biological-encounter denominator (Visit Authority
        # Budget + Ambiguous-Boundary Recall Closure v1): `None`/unset for
        # every ordinary product process -- this is explicitly scoped
        # field-validation tooling, never a normal product capability (see
        # docs/independent-encounter-denominator-design.md). Reading the
        # raw env var here, at process-construction time, rather than
        # inside `engine_runtime.py` itself keeps that module's own "no new
        # capture/recording capability without an explicit opt-in" contract
        # visible at the one place the whole app process is actually wired
        # together.
        recording_dir = os.environ.get(ACCEPTANCE_RECORDING_DIR_ENV)
        _observation_engine_session_manager = ObservationEngineSessionManager(
            repository_factory=ProductRepository,
            # So Start/Stop observing can deliberately pause/resume an
            # existing legacy live-view/monitoring camera session for the
            # same Stream instead of unknowingly competing with it for the
            # same physical Camera Node camera (see live_camera_session.
            # LiveCameraSessionManager.pause_for_observation).
            live_camera_sessions=get_live_camera_session_manager(),
            # Automatic Species Suggestion v1: the same app-wide, bounded
            # single-worker BioCLIP assist the legacy motion-review path
            # already uses (see `_maybe_schedule_automatic_review_
            # identification` below), so at most one automatic
            # identification ever runs at a time regardless of how many
            # Streams/paths triggered it.
            automatic_identification_assist=get_automatic_review_identification_assist(),
            acceptance_recording_root=Path(recording_dir) if recording_dir else None,
            # End-to-End Bird Encounter Recall Closure v1: reads the three
            # optional cadence/bound overrides (see their own docstrings in
            # acceptance_recorder.py) fresh at each real Start, not here --
            # `acceptance_recorder_config_from_env` is passed as the factory
            # itself rather than called now, so a later env-var change
            # before the *next* Start still takes effect. A no-op when
            # every override is unset, matching ordinary product behavior
            # byte-for-byte.
            acceptance_recorder_config_factory=acceptance_recorder_config_from_env,
        )
    return _observation_engine_session_manager


def get_tracked_activity_detector_manager() -> TrackedOutdoorActivityDetectorManager:
    """Return bounded, non-durable foreground/track state for live Streams."""

    global _tracked_activity_detector_manager
    if _tracked_activity_detector_manager is None:
        _tracked_activity_detector_manager = TrackedOutdoorActivityDetectorManager()
    return _tracked_activity_detector_manager


def get_live_object_detector_manager() -> LiveObjectDetectorManager:
    """One bounded local detector queue; created only by active monitoring work."""

    global _live_object_detector_manager
    if _live_object_detector_manager is None:
        _live_object_detector_manager = LiveObjectDetectorManager()
    return _live_object_detector_manager


def _release_overview_started_session(stream_id: str) -> None:
    """Release only a session the overview started; monitoring policy remains untouched."""

    if _live_camera_session_manager is None:
        return
    snapshot = _live_camera_session_manager.status(stream_id)
    if snapshot is None or snapshot.monitor_running:
        return
    runtime = get_repository().get_stream_runtime_status(stream_id)
    if runtime is not None and runtime.desired_mode == StreamMonitoringMode.armed:
        return
    _live_camera_session_manager.stop(stream_id, reason="overview_preview_released")


def get_live_preview_lease_manager() -> live_preview_leases.LivePreviewLeaseManager:
    global _live_preview_lease_manager
    if _live_preview_lease_manager is None:
        _live_preview_lease_manager = live_preview_leases.LivePreviewLeaseManager(
            on_expired_stream=_release_overview_started_session,
        )
    return _live_preview_lease_manager


def get_durable_monitoring_supervisor() -> DurableMonitoringSupervisor:
    """Return the single app-owned orchestrator without constructing a camera session."""

    global _durable_monitoring_supervisor
    if _durable_monitoring_supervisor is None:
        _durable_monitoring_supervisor = DurableMonitoringSupervisor(
            store=get_repository(),
            start_camera=_supervisor_start_camera,
            start_monitor=_supervisor_start_monitor,
            camera_status=_supervisor_camera_status,
            stop_camera=_supervisor_stop_camera,
        )
    return _durable_monitoring_supervisor


def _run_automatic_storage_maintenance() -> None:
    """Share one local maintenance window with backup and restore operations."""

    if not _backup_operation_lock.acquire(blocking=False):
        return
    try:
        repository = get_repository()
        settings = repository.storage_retention_settings()
        if not settings.automatic_cleanup_enabled:
            return
        repository.purge_expired_storage_recovery()
        repository.run_automatic_storage_retention()
    finally:
        _backup_operation_lock.release()


def get_local_storage_retention_service() -> LocalStorageRetentionService:
    """Return the single local maintenance scheduler; it never owns media policy."""

    global _local_storage_retention_service
    if _local_storage_retention_service is None:
        _local_storage_retention_service = LocalStorageRetentionService(
            run_maintenance=_run_automatic_storage_maintenance,
        )
    return _local_storage_retention_service


def _sync_local_storage_retention_service(*, enabled: bool) -> None:
    """Run the optional scheduler only while explicit durable policy permits it."""

    global _local_storage_retention_service
    if enabled:
        get_local_storage_retention_service().start()
    elif _local_storage_retention_service is not None:
        _local_storage_retention_service.shutdown()


def get_automatic_review_identification_assist() -> AutomaticReviewIdentificationAssist:
    global _automatic_review_identification_assist
    if _automatic_review_identification_assist is None:
        _automatic_review_identification_assist = AutomaticReviewIdentificationAssist()
    return _automatic_review_identification_assist


def _not_found(product_type: str, product_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"{product_type} '{product_id}' was not found.",
    )


def _unsupported_target(target_type: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=(
            f"Unsupported review target_type '{target_type}'. "
            "Supported target types are 'visit' and 'event'."
        ),
    )


def _invalid_zone_polygon() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail="Zone polygon must contain at least 3 points.",
    )


def _media_import_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "empty_file":
        return HTTPException(status_code=400, detail="Imported media file is empty.")
    if reason == "unsupported_content_type":
        return HTTPException(status_code=400, detail="Unsupported media content type.")
    if reason == "missing_stream":
        return _not_found("Stream", "import target")
    if reason == "missing_zone":
        return _not_found("Zone", "import target")
    if reason == "zone_stream_mismatch":
        return HTTPException(
            status_code=400,
            detail="Selected zone does not belong to the selected stream.",
        )
    if reason == "stream_required":
        return HTTPException(
            status_code=400,
            detail="Choose a stream for this media import.",
        )
    return HTTPException(status_code=400, detail="Media import could not be created.")


def _external_url_preview_warnings(
    configuration: SourceProviderConfiguration,
) -> list[str]:
    warnings: list[str] = []
    if any(
        configuration.safe_config_preview.get(field) == "configured"
        for field in ("auth_username", "auth_password")
    ):
        warnings.append(
            "Authentication metadata is configured but authenticated preview fetch "
            "is not implemented yet."
        )
    return warnings


def _resolve_external_url_save_stream_id(
    repository: ProductRepository,
    source_id: str,
    requested_stream_id: str | None,
) -> str:
    if requested_stream_id:
        stream = repository.get_stream(requested_stream_id)
        if stream is None:
            raise _not_found("Stream", requested_stream_id)
        if stream.source_id != source_id:
            raise HTTPException(
                status_code=400,
                detail="Selected stream does not belong to the external URL Source.",
            )
        return stream.id

    streams = repository.streams_for_source(source_id)
    if not streams:
        raise HTTPException(
            status_code=400,
            detail="Choose a stream before saving this external URL preview.",
        )
    return streams[0].id


def _folder_import_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "folder_required":
        return HTTPException(status_code=400, detail="Choose a local folder path.")
    if reason == "folder_missing":
        return HTTPException(status_code=404, detail="Folder was not found.")
    if reason == "folder_not_directory":
        return HTTPException(status_code=400, detail="Folder path must be a directory.")
    return _media_import_error(error)


def _folder_import_preview_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "folder_provider_required":
        return HTTPException(
            status_code=400,
            detail="Folder import preview requires a folder_import_future Source provider.",
        )
    if reason == "folder_required":
        return HTTPException(
            status_code=400, detail="Folder path metadata is required."
        )
    if reason == "folder_missing":
        return HTTPException(status_code=404, detail="Configured folder was not found.")
    if reason == "folder_not_directory":
        return HTTPException(
            status_code=400, detail="Configured folder must be a directory."
        )
    if reason == "folder_symlink":
        return HTTPException(
            status_code=400, detail="Configured folder must not be a symlink."
        )
    if reason == "folder_unavailable":
        return HTTPException(
            status_code=400, detail="Configured folder is unavailable."
        )
    return _media_import_error(error)


def _source_folder_import_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "folder_provider_required":
        return HTTPException(
            status_code=400,
            detail="Folder import requires a folder_import_future Source provider.",
        )
    if reason == "folder_required":
        return HTTPException(
            status_code=400, detail="Folder path metadata is required."
        )
    if reason == "folder_missing":
        return HTTPException(status_code=404, detail="Configured folder was not found.")
    if reason == "folder_not_directory":
        return HTTPException(
            status_code=400, detail="Configured folder must be a directory."
        )
    if reason == "folder_symlink":
        return HTTPException(
            status_code=400, detail="Configured folder must not be a symlink."
        )
    if reason == "folder_unavailable":
        return HTTPException(
            status_code=400, detail="Configured folder is unavailable."
        )
    if reason == "unsupported_copy_mode":
        return HTTPException(
            status_code=400, detail="Only copy_to_media_root is supported."
        )
    if reason == "stream_required":
        return HTTPException(
            status_code=400,
            detail="Choose a stream before importing folder media.",
        )
    if reason == "stream_source_mismatch":
        return HTTPException(
            status_code=400,
            detail="Selected stream does not belong to the folder import Source.",
        )
    if reason == "zone_blocked":
        return HTTPException(
            status_code=400,
            detail="Folder import cannot assign privacy or ignore zones.",
        )
    return _media_import_error(error)


def _detection_interface_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "missing_media_asset":
        return _not_found("Media asset", "detection input")
    if reason == "missing_stream":
        return _not_found("Stream", "detection input")
    if reason == "missing_zone":
        return _not_found("Zone", "detection input")
    if reason == "zone_stream_mismatch":
        return HTTPException(
            status_code=400,
            detail="Selected zone does not belong to the proposal stream.",
        )
    if reason == "media_stream_mismatch":
        return HTTPException(
            status_code=400,
            detail="Detection proposal stream must match the media asset stream.",
        )
    if reason == "proposal_already_decided":
        return HTTPException(
            status_code=400, detail="Detection proposal was already decided."
        )
    if reason == "unsupported_decision":
        return HTTPException(
            status_code=400, detail="Unsupported detection proposal decision."
        )
    return HTTPException(
        status_code=400, detail="Detection proposal could not be processed."
    )


def _model_adapter_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "missing_adapter":
        return _not_found("Model adapter", "adapter")
    if reason == "adapter_mismatch":
        return HTTPException(
            status_code=400, detail="Adapter id in path and payload must match."
        )
    if reason == "adapter_unavailable":
        return HTTPException(status_code=400, detail="Model adapter is not available.")
    if reason == "local_detector_not_configured":
        return HTTPException(
            status_code=400,
            detail=(
                "Local image detector model path is not configured. Set "
                "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH to a local model file before running it."
            ),
        )
    if reason == "local_detector_runtime_unavailable":
        return HTTPException(
            status_code=400,
            detail=(
                "Local image detector runtime is unavailable. Check the configured local model "
                "path and optional detector dependencies."
            ),
        )
    if reason == "megadetector_not_configured":
        return HTTPException(
            status_code=400,
            detail=(
                "MegaDetector model path is not configured. Set "
                "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH to a local MegaDetector-family model file "
                "before running it."
            ),
        )
    if reason == "megadetector_runtime_unavailable":
        return HTTPException(
            status_code=400,
            detail=(
                "MegaDetector runtime is unavailable. Install the optional "
                "detector-megadetector extra only when ready; no model files are "
                "bundled or downloaded automatically, and no reviewed truth was created."
            ),
        )
    if reason == "megadetector_model_file_missing":
        return HTTPException(
            status_code=404,
            detail=(
                "Configured MegaDetector model file was not found. Set "
                "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH to an existing local file."
            ),
        )
    if reason == "megadetector_model_format_unsupported":
        return HTTPException(
            status_code=400,
            detail=(
                "MegaDetector currently requires an existing local MDv5 .pt model file. "
                "Model aliases and automatic model downloads are not accepted."
            ),
        )
    if reason == "megadetector_model_checksum_mismatch":
        return HTTPException(
            status_code=400,
            detail=(
                "Configured MegaDetector model checksum does not match the approved "
                "local artifact. No inference, download, proposal, or reviewed truth was created."
            ),
        )
    if reason == "megadetector_failed":
        return HTTPException(
            status_code=400,
            detail=(
                "MegaDetector could not analyze this image. No proposal, reviewed truth, "
                "or export data was created."
            ),
        )
    if reason == "missing_media_file":
        return HTTPException(
            status_code=404,
            detail="Detector input media file was not found.",
        )
    if reason == "local_detector_unsupported_media_type":
        return HTTPException(
            status_code=400,
            detail=(
                "Local image detector supports imported image media only: "
                "image/jpeg, image/png, image/webp."
            ),
        )
    if reason == "megadetector_unsupported_media_type":
        return HTTPException(
            status_code=400,
            detail=(
                "MegaDetector adapter supports imported image media only: "
                "image/jpeg, image/png, image/webp."
            ),
        )
    if reason == "megadetector_zone_suppressed":
        return HTTPException(
            status_code=400,
            detail=(
                "MegaDetector analysis is disabled for Privacy and Ignore zones. "
                "No inference, proposal evidence, reviewed truth, or export data was created."
            ),
        )
    if reason == "unsupported_detector_output":
        return HTTPException(
            status_code=400,
            detail="Detector output format is not supported by this adapter path.",
        )
    if reason == "local_detector_failed":
        return HTTPException(
            status_code=400,
            detail="Local image detector failed cleanly. No truth or export data was created.",
        )
    if reason == "unsupported_media_type":
        return HTTPException(
            status_code=400,
            detail="Model adapter does not support this media type.",
        )
    return _detection_interface_error(error)


def _review_identification_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "unsupported_target":
        return HTTPException(
            status_code=400, detail="Unsupported review identification target."
        )
    if reason == "missing_review_candidate":
        return _not_found("Review Queue candidate", "identify target")
    return _model_adapter_error(error)


def _motion_evaluation_error(error: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


def _saved_media_motion_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "missing_media_file":
        return HTTPException(
            status_code=404,
            detail="Saved snapshot file was not found for motion check.",
        )
    if reason == "unsupported_image_content_type":
        return HTTPException(
            status_code=400,
            detail="Check motion supports saved image snapshots only.",
        )
    if reason == "image_decoder_unavailable":
        return HTTPException(
            status_code=400,
            detail=(
                "Captured frame could not be decoded for motion. "
                "Try recapturing or check image decoder support."
            ),
        )
    return HTTPException(
        status_code=400,
        detail=f"Saved snapshot could not be checked for motion: {reason}",
    )


def _motion_evidence_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "missing_source":
        return _not_found("Source", "motion evidence source")
    if reason == "missing_stream":
        return _not_found("Stream", "motion evidence stream")
    if reason == "missing_zone":
        return _not_found("Zone", "motion evidence zone")
    if reason == "missing_media_asset":
        return _not_found("Media asset", "motion evidence snapshot")
    if reason == "zone_stream_mismatch":
        return HTTPException(
            status_code=400,
            detail="Motion evidence zone does not belong to the selected stream.",
        )
    if reason == "stream_source_mismatch":
        return HTTPException(
            status_code=400,
            detail="Motion evidence stream does not belong to the selected source.",
        )
    if reason == "media_stream_mismatch":
        return HTTPException(
            status_code=400,
            detail="Motion evidence snapshot media must belong to the selected stream.",
        )
    if reason == "missing_media_file":
        return HTTPException(
            status_code=400,
            detail="Motion evidence media file is missing.",
        )
    if reason == "unsupported_motion_evidence_media_type":
        return HTTPException(
            status_code=400,
            detail="Motion Evidence can be created from supported still-image media only.",
        )
    if reason == "unsupported_duplicate_policy":
        return HTTPException(
            status_code=400,
            detail="Unsupported Motion Evidence duplicate policy.",
        )
    if reason == "motion_evidence_not_pending":
        return HTTPException(
            status_code=400,
            detail="Only pending Motion Evidence can be ignored.",
        )
    if reason == "motion_evidence_attach_ignored":
        return HTTPException(
            status_code=400,
            detail="Ignored Motion Evidence cannot change media attachment.",
        )
    if reason == "motion_evidence_attach_promoted":
        return HTTPException(
            status_code=400,
            detail="Promoted Motion Evidence cannot change media attachment.",
        )
    if reason == "motion_evidence_attach_not_pending":
        return HTTPException(
            status_code=400,
            detail="Only pending Motion Evidence can change media attachment.",
        )
    if reason == "motion_evidence_ignored":
        return HTTPException(
            status_code=400,
            detail="Ignored Motion Evidence cannot be promoted.",
        )
    if reason == "motion_evidence_already_promoted":
        return HTTPException(
            status_code=400,
            detail="Motion Evidence has already been promoted.",
        )
    if reason == "motion_evidence_promote_not_pending":
        return HTTPException(
            status_code=400,
            detail="Only pending Motion Evidence can be promoted.",
        )
    if reason == "motion_evidence_promote_empty":
        return HTTPException(
            status_code=400,
            detail="Promotion must create an Event or Visit.",
        )
    if reason == "motion_evidence_visit_requires_event":
        return HTTPException(
            status_code=400,
            detail="Motion Evidence promotion cannot create a Visit without an Event.",
        )
    if reason == "motion_evidence_zone_blocked":
        return HTTPException(
            status_code=400,
            detail="Motion Evidence in privacy or ignore zones cannot be promoted.",
        )
    if reason == "motion_evidence_creation_zone_blocked":
        return HTTPException(
            status_code=400,
            detail="Motion Evidence cannot be created for privacy or ignore zones.",
        )
    if reason == "missing_reviewable_zone":
        return HTTPException(
            status_code=400,
            detail="Choose a reviewable zone before creating Motion Evidence from saved media.",
        )
    return HTTPException(
        status_code=400, detail="Motion Evidence could not be processed."
    )


def _saved_preview_motion_evidence_error(
    error: ValueError,
    media_asset_id: str,
) -> HTTPException:
    if str(error) == "missing_media_asset":
        return _not_found("Media asset", media_asset_id)
    return _motion_evidence_error(error)


def _webhook_motion_evidence_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "webhook_provider_required":
        return HTTPException(
            status_code=400,
            detail="Webhook motion evidence requires a webhook_future Source provider.",
        )
    if reason == "webhook_motion_evidence_confirmation_required":
        return HTTPException(
            status_code=400,
            detail="Confirm this webhook motion payload before creating pending MotionEvidence.",
        )
    return _motion_evidence_error(error)


def _folder_import_evidence_dry_run_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "batch_dry_run_requires_selection":
        return HTTPException(
            status_code=400,
            detail="Choose MediaAssets, Source, or Stream for this folder evidence dry run.",
        )
    return _motion_evidence_error(error)


def _folder_import_evidence_batch_create_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "batch_create_requires_confirmation":
        return HTTPException(
            status_code=400,
            detail="Confirm this folder evidence batch before creating pending MotionEvidence.",
        )
    if reason == "batch_dry_run_requires_selection":
        return HTTPException(
            status_code=400,
            detail="Choose MediaAssets, Source, or Stream for this folder evidence batch.",
        )
    return _motion_evidence_error(error)


def _saved_media_cleanup_error(error: ValueError, media_asset_id: str) -> HTTPException:
    reason = str(error)
    if reason == "missing_media_asset":
        return _not_found("Media asset", media_asset_id)
    if reason == "cleanup_requires_confirmation":
        return HTTPException(
            status_code=400,
            detail="Confirm this file-only cleanup before deleting local saved preview media.",
        )
    if reason == "unsupported_cleanup_mode":
        return HTTPException(
            status_code=400,
            detail="Only delete_file_only cleanup is supported in this phase.",
        )
    return HTTPException(
        status_code=400,
        detail="Saved preview media cleanup could not be processed.",
    )


def _species_suggestion_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "missing_source":
        return _not_found("Source", "species suggestion source")
    if reason == "missing_stream":
        return _not_found("Stream", "species suggestion stream")
    if reason == "missing_event":
        return _not_found("Event", "species suggestion event")
    if reason == "missing_visit":
        return _not_found("Visit", "species suggestion visit")
    if reason == "missing_media_asset":
        return _not_found("Media asset", "species suggestion media")
    if reason == "missing_motion_evidence":
        return _not_found("Motion Evidence", "species suggestion evidence")
    if reason == "species_suggestion_not_pending":
        return HTTPException(
            status_code=400,
            detail="Only pending SpeciesSuggestion evidence can change status.",
        )
    return HTTPException(
        status_code=400, detail="SpeciesSuggestion could not be processed."
    )


def _species_candidate_pack_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason in {"candidate_pack_missing", "stream_missing"}:
        return HTTPException(
            status_code=404,
            detail="Species candidate pack or Stream was not found.",
        )
    messages = {
        "candidate_pack_name_invalid": "Enter a candidate-pack name up to 80 characters.",
        "candidate_pack_name_version_exists": "That candidate-pack name and version already exist.",
        "candidate_pack_member_count_invalid": "A candidate pack must contain between 2 and 200 bird species.",
        "candidate_pack_duplicate_member": "A candidate pack cannot contain the same bird twice.",
        "candidate_pack_unknown_taxonomy": "Choose bird species from the existing taxonomy.",
        "candidate_pack_members_must_be_bird_species": "Candidate packs may contain only existing bird species taxonomy labels.",
        "candidate_pack_builtin_immutable": "The built-in Backyard Core pack is immutable; clone it to customize it.",
        "candidate_pack_not_active": "Only active candidate packs can be edited or selected.",
    }
    return HTTPException(
        status_code=400,
        detail=messages.get(reason, "Species candidate pack could not be processed."),
    )


def _motion_zone_from_payload(zone: MotionZoneInput) -> MotionZone:
    return MotionZone(
        zone_id=zone.zone_id,
        left=zone.left,
        top=zone.top,
        right=zone.right,
        bottom=zone.bottom,
    )


def _sampler_zone_from_payload(zone: MotionZoneInput) -> SamplerZone:
    return SamplerZone(
        zone_id=zone.zone_id,
        left=zone.left,
        top=zone.top,
        right=zone.right,
        bottom=zone.bottom,
    )


def _motion_score_response(score: MotionScore) -> MotionScoreResponse:
    return MotionScoreResponse(
        zone_id=score.zone_id,
        changed_pixels=score.changed_pixels,
        total_pixels=score.total_pixels,
        changed_ratio=score.changed_ratio,
        mean_delta=score.mean_delta,
        triggered=score.triggered,
    )


def _motion_frame_score_response(
    frame_score: MotionFrameScore,
) -> MotionFrameScoreResponse:
    return MotionFrameScoreResponse(
        frame_index=frame_score.frame_index,
        scores=[_motion_score_response(score) for score in frame_score.scores],
        triggered_zone_ids=frame_score.triggered_zone_ids,
        strongest_zone_id=frame_score.strongest_zone_id,
        strongest_changed_ratio=frame_score.strongest_changed_ratio,
    )


def _motion_score_from_payload(score: MotionScoreResponse) -> MotionScore:
    return MotionScore(
        zone_id=score.zone_id,
        changed_pixels=score.changed_pixels,
        total_pixels=score.total_pixels,
        changed_ratio=score.changed_ratio,
        mean_delta=score.mean_delta,
        triggered=score.triggered,
    )


def _motion_frame_score_from_payload(
    frame_score: MotionFrameScoreResponse,
) -> MotionFrameScore:
    return MotionFrameScore(
        frame_index=frame_score.frame_index,
        scores=[_motion_score_from_payload(score) for score in frame_score.scores],
        triggered_zone_ids=frame_score.triggered_zone_ids,
        strongest_zone_id=frame_score.strongest_zone_id,
        strongest_changed_ratio=frame_score.strongest_changed_ratio,
    )


def _motion_candidate_response(candidate: MotionCandidate) -> MotionCandidateResponse:
    return MotionCandidateResponse(
        zone_id=candidate.zone_id,
        start_frame_index=candidate.start_frame_index,
        end_frame_index=candidate.end_frame_index,
        best_frame_index=candidate.best_frame_index,
        peak_changed_ratio=candidate.peak_changed_ratio,
        triggered_frame_count=candidate.triggered_frame_count,
    )


def _motion_zone_from_zone(zone: Zone) -> MotionZoneInput:
    xs = [point.x for point in zone.polygon]
    ys = [point.y for point in zone.polygon]
    return MotionZoneInput(
        zone_id=zone.id,
        left=max(0.0, min(xs)),
        top=max(0.0, min(ys)),
        right=min(1.0, max(xs)),
        bottom=min(1.0, max(ys)),
    )


@dataclass(frozen=True)
class _AutoMotionCell:
    region_id: str
    row: int
    column: int
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class _LiveActivitySuggestion:
    label: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class _LiveMotionZoneScoringPolicy:
    min_changed_ratio: float
    pixel_delta_threshold: float
    min_changed_pixels: int
    threshold_source: str
    fine_motion_applied: bool


@dataclass(frozen=True)
class _AutoMotionCluster:
    cells: list[_AutoMotionCell]
    start_frame_index: int
    end_frame_index: int
    best_frame_index: int
    peak_changed_ratio: float
    triggered_frame_count: int
    left: float
    top: float
    right: float
    bottom: float


_BIRD_FINE_MOTION_ZONE_TYPES = {ZoneType.feeder, ZoneType.birdbath, ZoneType.perch}
# Feeder birds occupied too few pixels at 64-wide field sampling. 160 keeps
# motion local and lightweight while making tiny pixel changes less dominant
# and preserving more useful zone detail for later detector enrichment.
_LIVE_ZONE_MOTION_MAX_DIMENSION = 160
_LIVE_TRACKED_ACTIVITY_MAX_DIMENSION = 640


def _tracked_zone_from_product_zone(zone: Zone) -> TrackedZone:
    return TrackedZone(
        zone_id=zone.id,
        zone_type=zone.zone_type.value,
        points=tuple((point.x, point.y) for point in zone.polygon),
        blocked=zone.zone_type.value in {"privacy", "ignore"},
    )


def _tracked_auto_area() -> TrackedZone:
    return TrackedZone(
        zone_id="auto-activity-area",
        zone_type="yard",
        points=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
    )


def _source_luminance_plane(data: bytes) -> np.ndarray:
    """Decode one cached still at its monitoring resolution for full-frame analysis."""

    decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if decoded is None or decoded.ndim != 2 or decoded.size == 0:
        raise SavedMediaFrameDecodeError("invalid_image")
    return decoded.astype(np.uint8, copy=False)


def _tracked_live_motion_result(
    *,
    stream_id: str,
    cached_frames: list[live_frame_cache.LiveFrame],
    source_luminance_frames: list[np.ndarray],
    zones: list[Zone],
    uses_auto_regions: bool,
    evaluated_at: datetime,
    preset: AnalysisPreset,
) -> TrackedActivityResult | None:
    """Track whole-stream foreground, then associate it with optional Zones.

    A normal Zone is product context, not a detector input boundary. Each
    fresh monitoring frame is privacy/ignore masked, aspect-preservingly bounded,
    and observed by the one Stream-owned foreground model. Regions that land
    in an enabled normal Zone inherit that context; every other usable-frame
    region remains general activity.
    """

    del uses_auto_regions  # Retained at the API seam for response compatibility.
    if not cached_frames or len(cached_frames) != len(source_luminance_frames):
        return None
    blocked_zones = [
        zone
        for zone in zones
        if zone.is_active and zone.zone_type.value in {"privacy", "ignore"}
    ]
    association_zones = [
        zone
        for zone in zones
        if zone.is_active
        and zone.zone_type.value not in {"privacy", "ignore"}
        and zone.monitoring_policy is not None
        and zone.monitoring_policy.monitoring_enabled
    ]
    tracked_zones = tuple(
        [_tracked_zone_from_product_zone(zone) for zone in association_zones]
        + [_tracked_auto_area()]
        + [_tracked_zone_from_product_zone(zone) for zone in blocked_zones]
    )
    result: TrackedActivityResult | None = None
    detector = get_tracked_activity_detector_manager().for_stream(
        stream_id, preset=preset
    )
    for cached_frame, source_frame in zip(
        cached_frames, source_luminance_frames, strict=True
    ):
        height, width = source_frame.shape
        cropped = _tracked_stream_analysis_frame(
            source_frame,
            blocked_zones=blocked_zones,
        )
        if cropped is None:
            continue
        analysis_frame, coordinate_box = cropped
        observed = detector.observe(
            analysis_frame,
            sequence=cached_frame.sequence,
            captured_at=cached_frame.captured_at,
            source_width=width,
            source_height=height,
            frame_identity=sha1(cached_frame.frame_bytes).hexdigest()[:20],
            zones=tracked_zones,
            coordinate_box=coordinate_box,
            now=evaluated_at,
        )
        result = TrackedActivityResult(
            telemetry=FrameTelemetry(
                source_width=width,
                source_height=height,
                analysis_width=observed.telemetry.analysis_width,
                analysis_height=observed.telemetry.analysis_height,
                frame_identity=observed.telemetry.frame_identity,
                captured_at=observed.telemetry.captured_at,
                frame_age_ms=observed.telemetry.frame_age_ms,
                duplicate_frame_count=observed.telemetry.duplicate_frame_count,
                dropped_frame_count=observed.telemetry.dropped_frame_count,
                frozen_frame_count=observed.telemetry.frozen_frame_count,
                accepted=observed.telemetry.accepted,
                ignored_reason=observed.telemetry.ignored_reason,
                zone_source_crop_width=width,
                zone_source_crop_height=height,
                analysis_zone_id="whole-stream",
            ),
            regions=observed.regions,
            tracks=observed.tracks,
            triggers=observed.triggers,
            foreground_mask=observed.foreground_mask,
            global_illumination_suppressed=observed.global_illumination_suppressed,
            foreground_model_state=observed.foreground_model_state,
        )
    return result


def _tracked_stream_analysis_frame(
    frame: np.ndarray,
    *,
    blocked_zones: list[Zone],
) -> tuple[np.ndarray, tuple[float, float, float, float]] | None:
    """Mask only Privacy/Ignore geometry and bound the full frame without stretch."""

    if frame.ndim != 2 or frame.size == 0:
        return None
    height, width = frame.shape
    usable = frame.copy()
    for blocked in blocked_zones:
        points = np.asarray(
            [
                [
                    round(max(0.0, min(1.0, point.x)) * (width - 1)),
                    round(max(0.0, min(1.0, point.y)) * (height - 1)),
                ]
                for point in blocked.polygon
            ],
            dtype=np.int32,
        )
        if len(points) >= 3:
            cv2.fillPoly(usable, [points], 0)
    longest_edge = max(width, height)
    scale = min(1.0, _LIVE_TRACKED_ACTIVITY_MAX_DIMENSION / float(longest_edge))
    if scale < 1.0:
        analysis = cv2.resize(
            usable,
            (
                max(1, round(width * scale)),
                max(1, round(height * scale)),
            ),
            interpolation=cv2.INTER_AREA,
        )
    else:
        analysis = usable
    return analysis.astype(np.uint8), (0.0, 0.0, 1.0, 1.0)

def _object_detector_monitoring_frame(
    frame_bytes: bytes,
    *,
    blocked_zones: list[Zone],
) -> tuple[bytes, tuple[float, float, float, float], int, int, int, int] | None:
    """Prepare the usable full monitoring frame for bounded live inference.

    Object detection is independent of foreground motion and Zone selection.
    Privacy and Ignore geometry is masked before the local model sees the
    frame; resizing preserves the monitoring frame's aspect ratio.
    """

    image = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.ndim != 3:
        return None
    source_height, source_width = image.shape[:2]
    if source_width < 2 or source_height < 2:
        return None
    usable = image.copy()
    mask = np.full(usable.shape[:2], 255, dtype=np.uint8)
    for blocked in blocked_zones:
        points = np.asarray(
            [
                [
                    round(max(0.0, min(1.0, point.x)) * (source_width - 1)),
                    round(max(0.0, min(1.0, point.y)) * (source_height - 1)),
                ]
                for point in blocked.polygon
            ],
            dtype=np.int32,
        )
        if len(points) >= 3:
            cv2.fillPoly(mask, [points], 0)
    if not np.any(mask):
        return None
    usable[mask == 0] = 0
    longest = max(usable.shape[:2])
    if longest > 1280:
        scale = 1280 / float(longest)
        usable = cv2.resize(
            usable,
            (
                max(1, round(usable.shape[1] * scale)),
                max(1, round(usable.shape[0] * scale)),
            ),
            interpolation=cv2.INTER_AREA,
        )
    encoded, output = cv2.imencode(".jpg", usable, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not encoded:
        return None
    image_bytes = output.tobytes()
    if not image_bytes or len(image_bytes) > 4_000_000:
        return None
    return (
        image_bytes,
        (0.0, 0.0, 1.0, 1.0),
        source_width,
        source_height,
        usable.shape[1],
        usable.shape[0],
    )


def _object_detection_zone_id(
    box: tuple[float, float, float, float],
    *,
    zones_by_id: dict[str, Zone],
) -> str:
    """Associate an observation after inference using centroid then overlap."""

    left, top, right, bottom = box
    center = ((left + right) / 2.0, (top + bottom) / 2.0)
    rectangle = np.asarray(
        [[left, top], [right, top], [right, bottom], [left, bottom]],
        dtype=np.float32,
    )
    box_area = max((right - left) * (bottom - top), 1e-9)
    candidates: list[tuple[bool, float, float, str]] = []
    for zone in zones_by_id.values():
        if not zone.is_active or zone.zone_type in {ZoneType.privacy, ZoneType.ignore}:
            continue
        polygon = np.asarray(
            [[point.x, point.y] for point in zone.polygon],
            dtype=np.float32,
        )
        if len(polygon) < 3:
            continue
        centroid_inside = cv2.pointPolygonTest(polygon, center, False) >= 0
        try:
            overlap, _ = cv2.intersectConvexConvex(
                cv2.convexHull(polygon), rectangle
            )
        except cv2.error:
            overlap = 0.0
        overlap_ratio = max(0.0, float(overlap)) / box_area
        if centroid_inside or overlap_ratio > 0.0:
            candidates.append(
                (
                    centroid_inside,
                    overlap_ratio,
                    abs(float(cv2.contourArea(polygon))),
                    zone.id,
                )
            )
    if not candidates:
        return "whole-stream"
    # Prefer a centroid match, then the greatest normalized overlap, then the
    # most specific Zone; IDs make ties stable across runs.
    return sorted(
        candidates,
        key=lambda item: (-int(item[0]), -item[1], item[2], item[3]),
    )[0][3]


def _associate_object_detector_zones(
    snapshot: ObjectDetectorSnapshot,
    *,
    zones_by_id: dict[str, Zone],
) -> ObjectDetectorSnapshot:
    """Project full-frame observations onto optional product Zone context."""

    def zone_id_for(box: tuple[float, float, float, float]) -> str:
        return _object_detection_zone_id(box, zones_by_id=zones_by_id)

    def associate_admission_item(item: dict[str, object]) -> dict[str, object]:
        values = dict(item)
        box = (
            values.get("left"),
            values.get("top"),
            values.get("right"),
            values.get("bottom"),
        )
        if all(isinstance(value, (int, float)) for value in box):
            values["zone_id"] = zone_id_for(box)  # type: ignore[arg-type]
        return values

    return replace(
        snapshot,
        detections=tuple(
            replace(detection, zone_id=zone_id_for(detection.box))
            for detection in snapshot.detections
        ),
        tracks=tuple(
            replace(track, zone_id=zone_id_for(track.box))
            for track in snapshot.tracks
        ),
        triggers=tuple(
            replace(trigger, zone_id=zone_id_for(trigger.box))
            for trigger in snapshot.triggers
        ),
        current_admission_candidates=tuple(
            associate_admission_item(item) for item in snapshot.current_admission_candidates
        ),
        recent_admission_outcomes=tuple(
            associate_admission_item(item) for item in snapshot.recent_admission_outcomes
        ),
    )


def _live_object_detector_result(
    *,
    stream_id: str,
    cached_frames: list[live_frame_cache.LiveFrame],
    zones_by_id: dict[str, Zone],
    blocked_zones: list[Zone],
) -> tuple[ObjectDetectorSnapshot, dict[str, int | str | None]]:
    """Continuously queue the latest usable monitoring frame for local MD."""

    manager = get_live_object_detector_manager()
    metadata: dict[str, int | str | None] = {
        "zone_id": "whole-stream",
        "source_width": None,
        "source_height": None,
        "input_width": None,
        "input_height": None,
    }
    if not cached_frames:
        return _associate_object_detector_zones(
            manager.poll(stream_id), zones_by_id=zones_by_id
        ), metadata
    frame = cached_frames[-1]
    prepared = _object_detector_monitoring_frame(
        frame.frame_bytes,
        blocked_zones=blocked_zones,
    )
    if prepared is None:
        return _associate_object_detector_zones(
            manager.poll(stream_id), zones_by_id=zones_by_id
        ), metadata
    image, coordinate_box, source_width, source_height, input_width, input_height = prepared
    metadata.update(
        {
            "source_width": source_width,
            "source_height": source_height,
            "input_width": input_width,
            "input_height": input_height,
        }
    )
    manager.submit(
        stream_id=stream_id,
        zone_id="whole-stream",
        zone_type="whole_stream",
        frame_identity=sha1(frame.frame_bytes).hexdigest()[:20],
        sequence=frame.sequence,
        captured_at=frame.captured_at,
        coordinate_box=coordinate_box,
        image=image,
    )
    return _associate_object_detector_zones(
        manager.poll(stream_id), zones_by_id=zones_by_id
    ), metadata

def _object_track_motion_candidate(
    trigger: ObjectTrackTrigger,
    *,
    sequence_by_identity: dict[str, int],
    fallback_sequence: int,
) -> MotionCandidate:
    sequence = sequence_by_identity.get(trigger.frame_identity, fallback_sequence)
    return MotionCandidate(
        zone_id=trigger.zone_id,
        start_frame_index=sequence,
        end_frame_index=sequence,
        best_frame_index=sequence,
        peak_changed_ratio=trigger.score,
        triggered_frame_count=1,
    )


def _object_trigger_region(
    trigger: ObjectTrackTrigger,
    *,
    source_width: int,
    source_height: int,
) -> MotionRegion:
    left, top, right, bottom = trigger.box
    return MotionRegion(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        centroid_x=(left + right) / 2,
        centroid_y=(top + bottom) / 2,
        pixel_area=max(1, round((right - left) * (bottom - top) * source_width * source_height)),
        zone_relative_area=max(0.0, (right - left) * (bottom - top)),
        mask_occupancy=1.0,
        zone_id=trigger.zone_id,
        frame_identity=trigger.frame_identity,
        captured_at=trigger.captured_at,
    )


def _tracked_trigger_region(
    trigger: TrackTrigger,
    *,
    source_width: int,
    source_height: int,
) -> MotionRegion:
    """Adapt a coherent foreground track into its exact capture geometry."""

    left, top, right, bottom = trigger.box
    return MotionRegion(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        centroid_x=(left + right) / 2,
        centroid_y=(top + bottom) / 2,
        pixel_area=max(
            1, round((right - left) * (bottom - top) * source_width * source_height)
        ),
        zone_relative_area=max(0.0, (right - left) * (bottom - top)),
        mask_occupancy=1.0,
        zone_id=trigger.zone_id,
        frame_identity=trigger.best_frame_identity
        or trigger.first_frame_identity
        or "",
        captured_at=trigger.captured_at,
    )


def _tracked_sampler_result(
    tracked: TrackedActivityResult | None,
    *,
    cached_frames: list[live_frame_cache.LiveFrame],
    zones_by_id: dict[str, Zone],
) -> SamplerResult:
    """Preserve the existing response shape without using ratio scoring as a trigger."""

    if tracked is None:
        return SamplerResult(frame_scores=[], candidates=[])
    tracks_by_key = {
        (track.track_id, zone_id): track
        for track in tracked.tracks
        for zone_id in track.zone_ids
    }
    sequence_by_identity = {
        sha1(frame.frame_bytes).hexdigest()[:20]: frame.sequence for frame in cached_frames
    }
    scores_by_zone: dict[str, MotionScore] = {}
    for region in tracked.regions:
        current = scores_by_zone.get(region.zone_id)
        total = max(1, int(region.pixel_area / max(region.zone_relative_area, 1e-9)))
        score = MotionScore(
            zone_id=region.zone_id,
            changed_pixels=region.pixel_area,
            total_pixels=total,
            changed_ratio=region.zone_relative_area,
            mean_delta=0.0,
            triggered=any(
                trigger.zone_id == region.zone_id for trigger in tracked.triggers
            ),
        )
        if current is None or score.changed_pixels > current.changed_pixels:
            scores_by_zone[region.zone_id] = score
    candidates: list[MotionCandidate] = []
    for trigger in tracked.triggers:
        track = tracks_by_key.get((trigger.track_id, trigger.zone_id))
        if track is None:
            continue
        best_sequence = sequence_by_identity.get(
            trigger.best_frame_identity or "", cached_frames[-1].sequence
        )
        start_sequence = sequence_by_identity.get(
            trigger.first_frame_identity or "", best_sequence
        )
        candidates.append(
            MotionCandidate(
                zone_id=trigger.zone_id,
                start_frame_index=start_sequence,
                end_frame_index=best_sequence,
                best_frame_index=best_sequence,
                peak_changed_ratio=max(
                    0.0,
                    next(
                        (
                            region.zone_relative_area
                            for region in tracked.regions
                            if region.zone_id == trigger.zone_id
                        ),
                        0.0,
                    ),
                ),
                triggered_frame_count=track.hit_count,
            )
        )
    scores = list(scores_by_zone.values())
    frame_score = MotionFrameScore(
        frame_index=cached_frames[-1].sequence,
        scores=scores,
        triggered_zone_ids=[candidate.zone_id for candidate in candidates],
        strongest_zone_id=(
            max(scores, key=lambda score: score.changed_pixels).zone_id if scores else None
        ),
        strongest_changed_ratio=(
            max((score.changed_ratio for score in scores), default=0.0)
        ),
    )
    return SamplerResult(frame_scores=[frame_score], candidates=candidates)


def _tracked_pretrigger_live_frames(
    tracked: TrackedActivityResult | None,
    *,
    cached_frames: list[live_frame_cache.LiveFrame],
    frame_summaries: list[LiveMotionFrameSummary],
    zone_id: str | None,
    track_generation_id: str | None = None,
) -> list[dict[str, Any]]:
    """Resolve the detector's tiny identity ring back to original cached bytes."""

    if tracked is None or zone_id is None:
        return []
    trigger = next(
        (
            item
            for item in tracked.triggers
            if item.zone_id == zone_id
            and (track_generation_id is None or item.track_generation_id == track_generation_id)
        ),
        None,
    )
    if trigger is None:
        return []
    requested = set(trigger.pretrigger_frame_identities)
    if not requested:
        return []
    summaries = {summary.sequence: summary for summary in frame_summaries}
    frames: list[dict[str, Any]] = []
    for frame in cached_frames:
        identity = sha1(frame.frame_bytes).hexdigest()[:20]
        if identity not in requested:
            continue
        summary = summaries.get(frame.sequence)
        frames.append(
            {
                "sequence": frame.sequence,
                "captured_at": frame.captured_at,
                "frame_bytes": frame.frame_bytes,
                "content_type": frame.content_type,
                # The bytes remain at source resolution.  Analysis dimensions
                # are metadata only and never cause a resized evidence write.
                "width": summary.width if summary else None,
                "height": summary.height if summary else None,
            }
        )
    return frames[:2]


def _object_pretrigger_live_frames(
    trigger: ObjectTrackTrigger,
    *,
    cached_frames: list[live_frame_cache.LiveFrame],
    frame_summaries: list[LiveMotionFrameSummary],
) -> list[dict[str, Any]]:
    """Retain at most two cached monitoring frames as object-track context."""

    trigger_sequence = next(
        (
            frame.sequence
            for frame in cached_frames
            if sha1(frame.frame_bytes).hexdigest()[:20] == trigger.frame_identity
        ),
        None,
    )
    if trigger_sequence is None:
        return []
    dimensions = {summary.sequence: summary for summary in frame_summaries}
    return [
        {
            "sequence": frame.sequence,
            "captured_at": frame.captured_at,
            "frame_bytes": frame.frame_bytes,
            "content_type": frame.content_type,
            "width": dimensions.get(frame.sequence).width
            if dimensions.get(frame.sequence)
            else None,
            "height": dimensions.get(frame.sequence).height
            if dimensions.get(frame.sequence)
            else None,
        }
        for frame in cached_frames
        if frame.sequence < trigger_sequence
    ][-2:]


def _tracked_activity_evidence_payload(
    tracked: TrackedActivityResult | None,
    object_detector: ObjectDetectorSnapshot | None = None,
) -> dict[str, Any]:
    """Keep bounded tracker facts as observational provenance, never truth."""

    payload: dict[str, Any] = {
        "pipeline": "opencv_mog2_region_track",
        "foreground_model_state": tracked.foreground_model_state if tracked else None,
        "verified": False,
        "frame_identity": tracked.telemetry.frame_identity if tracked else None,
        "analysis_dimensions": (
            [tracked.telemetry.analysis_width, tracked.telemetry.analysis_height]
            if tracked
            else []
        ),
        "source_dimensions": (
            [tracked.telemetry.source_width, tracked.telemetry.source_height]
            if tracked
            else []
        ),
        "duplicate_frame_count": tracked.telemetry.duplicate_frame_count if tracked else 0,
        "dropped_frame_count": tracked.telemetry.dropped_frame_count if tracked else 0,
        "regions": [
            {
                "left": region.left,
                "top": region.top,
                "right": region.right,
                "bottom": region.bottom,
                "pixel_area": region.pixel_area,
                "zone_id": region.zone_id,
            }
            for region in (tracked.regions[:8] if tracked else ())
        ],
        "tracks": [
            {
                "track_id": track.track_id,
                "track_generation_id": track.track_generation_id,
                "state": track.state,
                "hit_count": track.hit_count,
                "missed_frame_count": track.missed_frame_count,
                "zone_ids": list(track.zone_ids),
                "best_frame_identity": track.best_frame_identity,
                "triggered": track.triggered,
            }
            for track in (tracked.tracks[:8] if tracked else ())
        ],
        "triggers": [
            {
                "track_id": trigger.track_id,
                "track_generation_id": trigger.track_generation_id,
                "zone_id": trigger.zone_id,
                "box": list(trigger.box),
                "reason": trigger.reason,
                "verified": trigger.verified,
                "pretrigger_frame_identities": list(
                    trigger.pretrigger_frame_identities
                ),
            }
            for trigger in (tracked.triggers[:8] if tracked else ())
        ],
    }
    if object_detector is not None:
        payload["object_detector"] = {
            **detector_provenance(),
            "detections": [item.as_dict() for item in object_detector.detections[:8]],
            "tracks": [item.as_dict() for item in object_detector.tracks[:8]],
            "triggers": [
                {
                    "track_id": item.track_id,
                    "track_generation_id": item.track_generation_id,
                    "zone_id": item.zone_id,
                    "class": item.label,
                    "score": item.score,
                    "box": list(item.box),
                    "frame_identity": item.frame_identity,
                    "captured_at": item.captured_at,
                    "trigger_reason": "object_verified",
                }
                for item in object_detector.triggers[:8]
            ],
            "inference_latency_ms": object_detector.inference_latency_ms,
            "queue_depth": object_detector.queue_depth,
            "dropped_frame_count": object_detector.dropped_frame_count,
            "stale_frame_count": object_detector.stale_frame_count,
            "unavailable_reason": object_detector.unavailable_reason,
        }
    return payload


def _tracked_foreground_mask_data_url(
    tracked: TrackedActivityResult | None,
) -> str | None:
    if tracked is None or tracked.foreground_mask is None:
        return None
    encoded, data = cv2.imencode(".png", tracked.foreground_mask)
    if not encoded or len(data) > 750_000:
        return None
    return "data:image/png;base64," + base64.b64encode(data.tobytes()).decode("ascii")


def _motion_zone_from_bounds(
    *,
    zone_id: str,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> MotionZoneInput:
    return MotionZoneInput(
        zone_id=zone_id,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
    )


def _activity_area_from_zone(zone: Zone) -> MotionActivityAreaResponse:
    bounds = _motion_zone_from_zone(zone)
    return MotionActivityAreaResponse(
        area_id=zone.id,
        label=zone.name,
        source="user_zone",
        left=bounds.left,
        top=bounds.top,
        right=bounds.right,
        bottom=bounds.bottom,
        zone_id=zone.id,
    )


def _activity_area_zone_input(area: MotionActivityAreaResponse) -> MotionZoneInput:
    return _motion_zone_from_bounds(
        zone_id=area.area_id,
        left=area.left,
        top=area.top,
        right=area.right,
        bottom=area.bottom,
    )


def _suppressed_zone_reason(zone: Zone) -> str:
    if zone.zone_type.value == "privacy":
        return "privacy_zone"
    if zone.zone_type.value == "ignore":
        return "ignore_zone"
    return "suppressed_zone"


def _zone_motion_summary_label(
    summaries: list[MotionSuppressedZoneSummaryResponse],
) -> str:
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0].zone_name
    other_count = len(summaries) - 1
    return (
        f"{summaries[0].zone_name} and {other_count} other ignored/privacy "
        f"zone{'s' if other_count != 1 else ''}"
    )


def _motion_suppressed_zone_summaries(
    frames: list[list[list[int | float]]],
    blocked_zones: list[Zone],
    config: SamplerConfig,
) -> list[MotionSuppressedZoneSummaryResponse]:
    if not frames or not blocked_zones:
        return []

    suppressed_config = SamplerConfig(
        pixel_delta_threshold=config.pixel_delta_threshold,
        min_changed_ratio=config.min_changed_ratio,
        min_triggered_frames=config.min_triggered_frames,
        max_gap_frames=config.max_gap_frames,
        frame_index_start=config.frame_index_start,
        create_motion_evidence=False,
    )
    try:
        result = evaluate_sampled_frame_sequence(
            frames,
            [
                _sampler_zone_from_payload(_motion_zone_from_zone(zone))
                for zone in blocked_zones
            ],
            suppressed_config,
        )
    except ValueError:
        return []

    zones_by_id = {zone.id: zone for zone in blocked_zones}
    summaries: list[MotionSuppressedZoneSummaryResponse] = []
    for candidate in result.candidates:
        zone = zones_by_id.get(candidate.zone_id)
        if zone is None:
            continue
        summaries.append(
            MotionSuppressedZoneSummaryResponse(
                zone_id=zone.id,
                zone_name=zone.name,
                zone_type=zone.zone_type,
                reason=_suppressed_zone_reason(zone),
                triggered_frame_count=candidate.triggered_frame_count,
                peak_changed_ratio=candidate.peak_changed_ratio,
            )
        )

    return sorted(
        summaries,
        key=lambda summary: (summary.peak_changed_ratio, summary.triggered_frame_count),
        reverse=True,
    )


def _motion_activity_summary(
    *,
    activity_detected: bool,
    strongest_zone_name: str | None,
    strongest_activity_area_label: str | None,
    uses_auto_regions: bool,
    suppressed_zone_summaries: list[MotionSuppressedZoneSummaryResponse],
) -> str:
    if activity_detected:
        if strongest_zone_name:
            return f"Activity detected in {strongest_zone_name}."
        if strongest_activity_area_label:
            return f"Activity detected in {strongest_activity_area_label}."
        if uses_auto_regions:
            return "Activity detected in automatic activity area."
        return "Activity detected."

    if suppressed_zone_summaries:
        return f"Motion ignored in {_zone_motion_summary_label(suppressed_zone_summaries)}."

    return "No activity detected."


def _live_activity_suggestion_for_zone(
    zone_type: ZoneType | None,
    zone_name: str | None,
) -> _LiveActivitySuggestion | None:
    if zone_type in {ZoneType.feeder, ZoneType.birdbath, ZoneType.perch}:
        return _LiveActivitySuggestion(
            label="unknown_bird",
            confidence=0.30,
            reason=(
                f"Low-confidence live motion suggestion from {zone_name or 'bird-focused'} "
                "Zone context. Confirm or correct in Review Queue."
            ),
        )
    if zone_type in {ZoneType.ground, ZoneType.yard, ZoneType.driveway}:
        return _LiveActivitySuggestion(
            label="unknown_animal",
            confidence=0.25,
            reason=(
                f"Low-confidence live motion suggestion from {zone_name or 'outdoor'} "
                "Zone context. Confirm or correct in Review Queue."
            ),
        )
    return None


def _live_zone_min_changed_ratio(
    *,
    zone_type: ZoneType | None,
    base_min_changed_ratio: float,
    focus_applied: bool = False,
    pixel_delta_threshold: float = 25.0,
    bird_sized_feeder_motion: bool = True,
) -> float:
    return _live_motion_zone_scoring_policy(
        zone_type=zone_type,
        base_min_changed_ratio=base_min_changed_ratio,
        pixel_delta_threshold=pixel_delta_threshold,
        focus_applied=focus_applied,
        bird_sized_feeder_motion=bird_sized_feeder_motion,
    ).min_changed_ratio


def _live_motion_zone_scoring_policy(
    *,
    zone_type: ZoneType | None,
    zone_policy: ZoneMonitoringPolicy | None = None,
    base_min_changed_ratio: float,
    pixel_delta_threshold: float,
    focus_applied: bool = False,
    bird_sized_feeder_motion: bool = True,
) -> _LiveMotionZoneScoringPolicy:
    policy_base_ratio = base_min_changed_ratio
    if zone_policy is not None:
        if zone_policy.activity_sensitivity == ZoneActivitySensitivity.low:
            policy_base_ratio *= 2.0
        elif (
            zone_policy.activity_sensitivity == ZoneActivitySensitivity.high
            and "activity_sensitivity" in zone_policy.customized_fields
            and (not bird_sized_feeder_motion or zone_type not in _BIRD_FINE_MOTION_ZONE_TYPES)
        ):
            # Bird-focused Zones already receive the established fine-motion path.
            policy_base_ratio *= 0.5

    if not bird_sized_feeder_motion or zone_type not in _BIRD_FINE_MOTION_ZONE_TYPES:
        return _LiveMotionZoneScoringPolicy(
            min_changed_ratio=policy_base_ratio,
            pixel_delta_threshold=pixel_delta_threshold,
            min_changed_pixels=1,
            threshold_source="requested",
            fine_motion_applied=False,
        )

    threshold = max(0.001, policy_base_ratio * 0.5)
    effective_pixel_delta = pixel_delta_threshold
    threshold_source = f"bird_{zone_type.value}_fine"
    high_sensitivity = policy_base_ratio <= 0.004 or pixel_delta_threshold <= 12
    if high_sensitivity:
        threshold = max(0.0008, min(threshold, policy_base_ratio / 3.0))
        effective_pixel_delta = min(pixel_delta_threshold, 8.0)
        threshold_source = f"bird_{zone_type.value}_high_fine"

    if focus_applied:
        threshold = max(0.0005, threshold * 0.5)
        threshold_source = (
            f"bird_{zone_type.value}_high_focus_fine"
            if high_sensitivity
            else f"bird_{zone_type.value}_focus_fine"
        )

    return _LiveMotionZoneScoringPolicy(
        min_changed_ratio=threshold,
        pixel_delta_threshold=effective_pixel_delta,
        min_changed_pixels=2,
        threshold_source=threshold_source,
        fine_motion_applied=True,
    )


def _live_motion_sampler_result(
    frames: list[list[list[int | float]]],
    motion_zones: list[MotionZoneInput],
    zones_by_id: dict[str, Zone],
    config: SamplerConfig,
    *,
    focus_zone_id: str | None = None,
    bird_sized_feeder_motion: bool = True,
) -> SamplerResult:
    frame_scores: list[MotionFrameScore] = []
    motion_zone_by_id = {
        zone.zone_id: MotionZone(
            zone_id=zone.zone_id,
            left=zone.left,
            top=zone.top,
            right=zone.right,
            bottom=zone.bottom,
        )
        for zone in motion_zones
    }

    for pair_index in range(len(frames) - 1):
        scores: list[MotionScore] = []
        for zone in motion_zones:
            zone_model = zones_by_id.get(zone.zone_id)
            zone_type = zone_model.zone_type if zone_model is not None else None
            zone_policy = zone_model.monitoring_policy if zone_model is not None else None
            zone_focus_applied = focus_zone_id is not None and zone.zone_id == focus_zone_id
            scoring_policy = _live_motion_zone_scoring_policy(
                zone_type=zone_type,
                zone_policy=zone_policy,
                base_min_changed_ratio=config.min_changed_ratio,
                pixel_delta_threshold=config.pixel_delta_threshold,
                focus_applied=zone_focus_applied,
                bird_sized_feeder_motion=bird_sized_feeder_motion,
            )
            score = score_zone_motion(
                frames[pair_index],
                frames[pair_index + 1],
                motion_zone_by_id[zone.zone_id],
                pixel_delta_threshold=scoring_policy.pixel_delta_threshold,
                min_changed_ratio=scoring_policy.min_changed_ratio,
            )
            if (
                score.triggered
                and score.changed_pixels < scoring_policy.min_changed_pixels
            ):
                score = MotionScore(
                    zone_id=score.zone_id,
                    changed_pixels=score.changed_pixels,
                    total_pixels=score.total_pixels,
                    changed_ratio=score.changed_ratio,
                    mean_delta=score.mean_delta,
                    triggered=False,
                )
            scores.append(score)
        triggered_zone_ids = [score.zone_id for score in scores if score.triggered]
        strongest_score = max(
            scores, key=lambda score: score.changed_ratio, default=None
        )
        frame_scores.append(
            MotionFrameScore(
                frame_index=config.frame_index_start + pair_index + 1,
                scores=scores,
                triggered_zone_ids=triggered_zone_ids,
                strongest_zone_id=strongest_score.zone_id if strongest_score else None,
                strongest_changed_ratio=(
                    strongest_score.changed_ratio if strongest_score else 0.0
                ),
            )
        )

    return SamplerResult(
        frame_scores=frame_scores,
        candidates=extract_motion_candidates(
            frame_scores,
            min_triggered_frames=config.min_triggered_frames,
            max_gap_frames=config.max_gap_frames,
        ),
    )


def _live_motion_pair_sequences(
    frames: list[live_frame_cache.LiveFrame],
    frame_sequence: int | None,
) -> tuple[int | None, int | None]:
    if frame_sequence is None:
        return None, None
    for index, frame in enumerate(frames):
        if frame.sequence == frame_sequence:
            previous = frames[index - 1].sequence if index > 0 else None
            return previous, frame.sequence
    return None, None


def _strongest_live_motion_score(
    frame_scores: list[MotionFrameScoreResponse],
    *,
    strongest_zone_id: str | None,
) -> tuple[MotionScoreResponse | None, int | None]:
    best_score: MotionScoreResponse | None = None
    best_frame_index: int | None = None
    for frame_score in frame_scores:
        for score in frame_score.scores:
            if strongest_zone_id is not None and score.zone_id != strongest_zone_id:
                continue
            if best_score is None or score.changed_ratio > best_score.changed_ratio:
                best_score = score
                best_frame_index = frame_score.frame_index
    return best_score, best_frame_index


def _live_motion_margin_to_threshold(
    *,
    strongest_changed_ratio: float,
    effective_threshold: float | None,
) -> float | None:
    if effective_threshold is None:
        return None
    return strongest_changed_ratio - effective_threshold


def _live_motion_near_miss(
    *,
    activity_detected: bool,
    strongest_score: MotionScoreResponse | None,
    effective_threshold: float | None,
    scoring_policy: _LiveMotionZoneScoringPolicy | None,
) -> bool:
    if activity_detected or strongest_score is None or effective_threshold is None:
        return False
    if (
        scoring_policy is not None
        and strongest_score.changed_pixels < scoring_policy.min_changed_pixels
    ):
        return False
    return (
        strongest_score.changed_ratio < effective_threshold
        and strongest_score.changed_ratio >= effective_threshold * 0.6
    )


def _format_motion_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    percent = value * 100
    return f"{percent:.2f}%"


def _live_motion_diagnostic_message(
    *,
    activity_detected: bool,
    near_miss: bool,
    strongest_zone_name: str | None,
    strongest_zone_type: ZoneType | None,
    strongest_changed_ratio: float,
    effective_threshold: float | None,
    fine_motion_applied: bool,
) -> str | None:
    if strongest_zone_name is None or effective_threshold is None:
        return None

    changed = _format_motion_percent(strongest_changed_ratio)
    threshold = _format_motion_percent(effective_threshold)
    if activity_detected and fine_motion_applied:
        return (
            f"Bird-sized motion detected - {strongest_zone_name} changed {changed}, "
            f"threshold {threshold}."
        )
    if near_miss:
        prefix = (
            "No bird-sized activity yet"
            if fine_motion_applied
            and strongest_zone_type in _BIRD_FINE_MOTION_ZONE_TYPES
            else f"Near miss in {strongest_zone_name}"
        )
        return (
            f"{prefix} - {strongest_zone_name} changed {changed}, "
            f"threshold {threshold}. Try tighter feeder zone or move camera closer."
        )
    if not activity_detected:
        prefix = (
            "No bird-sized activity yet"
            if fine_motion_applied
            and strongest_zone_type in _BIRD_FINE_MOTION_ZONE_TYPES
            else "No activity yet"
        )
        return (
            f"{prefix} - {strongest_zone_name} changed {changed}, "
            f"threshold {threshold}. Try tighter zones or adjust camera framing."
        )
    return None


def _live_motion_zone_context_warnings(
    *,
    strongest_zone: Zone | None,
    reviewable_zones: list[Zone],
) -> list[str]:
    if strongest_zone is None:
        return []

    warnings: list[str] = []
    bird_zones_available = any(
        zone.zone_type in _BIRD_FINE_MOTION_ZONE_TYPES for zone in reviewable_zones
    )
    if bird_zones_available and strongest_zone.zone_type in {
        ZoneType.ground,
        ZoneType.yard,
        ZoneType.driveway,
    }:
        warnings.append(
            f"Strongest motion is in {strongest_zone.name}, not a feeder/birdbath/perch "
            "Zone. For birds, draw a tight Feeder Zone around the perch or feeding ports."
        )

    if strongest_zone.zone_type in {ZoneType.yard, ZoneType.driveway} and (
        _zone_bounding_area(strongest_zone) >= 0.25
    ):
        warnings.append(
            f"{strongest_zone.name} covers a broad background area; use Ignore zones for "
            "road, cars, or background movement."
        )

    return warnings


def _live_motion_ignore_suppression_warning(
    summary: MotionSuppressedZoneSummaryResponse,
) -> str:
    zone_kind = summary.zone_type.value.replace("_", " ")
    article = "an" if zone_kind[0].lower() in {"a", "e", "i", "o", "u"} else "a"
    return (
        f"Strongest motion is in {summary.zone_name}; review candidate suppressed "
        f"because it is {article} {zone_kind} Zone."
    )


def _live_motion_quality_warnings(
    frames: list[SavedMediaFrame],
    zones: list[Zone],
) -> list[str]:
    if not frames:
        return []

    latest_pixels = [pixel for row in frames[-1].frame for pixel in row]
    if not latest_pixels:
        return []

    warnings: list[str] = []
    pixel_count = len(latest_pixels)
    mean_value = sum(latest_pixels) / pixel_count
    contrast_range = max(latest_pixels) - min(latest_pixels)
    mean_delta = sum(abs(pixel - mean_value) for pixel in latest_pixels) / pixel_count
    clipped_highlight_ratio = sum(pixel >= 245 for pixel in latest_pixels) / pixel_count
    clipped_shadow_ratio = sum(pixel <= 10 for pixel in latest_pixels) / pixel_count

    # Downsampling softens white clipping, so a bright frame can lose useful
    # identification detail before a majority of sampled pixels remain at 245+.
    if (mean_value >= 235 and contrast_range <= 35) or (
        mean_value >= 200 and clipped_highlight_ratio >= 0.40
    ):
        warnings.append(
            "Camera image appears overexposed with clipped highlights; lower exposure or "
            "disable low-light compensation in camera controls."
        )
    elif (mean_value <= 20 and contrast_range <= 35) or clipped_shadow_ratio >= 0.65:
        warnings.append(
            "Camera image appears underexposed with clipped shadows; raise exposure in "
            "camera controls."
        )
    if contrast_range <= 14 or mean_delta <= 5:
        warnings.append(
            "Camera image appears low contrast; motion may be harder to detect."
        )

    for zone in zones:
        if zone.zone_type not in {ZoneType.feeder, ZoneType.birdbath, ZoneType.perch}:
            continue
        if _zone_bounding_area(zone) < 0.05:
            warnings.append(
                f"{zone.name} is small in frame; use tighter framing or focus for monitoring."
            )
            break

    return warnings


def _zone_bounding_area(zone: Zone) -> float:
    if not zone.polygon:
        return 0.0
    min_x = min(point.x for point in zone.polygon)
    max_x = max(point.x for point in zone.polygon)
    min_y = min(point.y for point in zone.polygon)
    max_y = max(point.y for point in zone.polygon)
    return max(0.0, max_x - min_x) * max(0.0, max_y - min_y)


def _latest_species_suggestion_for_visit(
    repository: ProductRepository,
    visit_id: str | None,
) -> SpeciesSuggestionResponse | None:
    if visit_id is None:
        return None
    suggestions = repository.list_species_suggestions(visit_id=visit_id)
    return suggestions[-1] if suggestions else None


def _live_frame_cache_response_fields(
    status: live_frame_cache.LiveFrameCacheStatus,
) -> dict[str, int | bool | datetime | None]:
    return {
        "frames_available": status.recent_frame_count,
        "recent_frame_count": status.recent_frame_count,
        "newest_frame_age_ms": status.newest_frame_age_ms,
        "oldest_frame_age_ms": status.oldest_frame_age_ms,
        "newest_frame_sequence": status.newest_frame_sequence,
        "buffer_capacity": status.buffer_capacity,
        "fresh_enough": status.fresh_enough,
        "last_frame_at": status.last_frame_at,
    }


def _live_activity_session_status_fields(
    activity: dict[str, Any] | None,
    *,
    quiet_seconds: int = DEFAULT_QUIET_PERIOD_SECONDS,
) -> dict[str, Any]:
    if not activity:
        return {}
    quiet_remaining_seconds = _live_activity_quiet_remaining_seconds(
        activity,
        quiet_seconds=quiet_seconds,
    )
    return {
        "current_activity_session": activity,
        "current_activity_session_id": activity.get("activity_session_id"),
        "activity_started_at": activity.get("started_at"),
        "activity_last_seen_at": activity.get("last_seen_at"),
        "activity_detection_count": activity.get("detection_count") or 0,
        "activity_near_miss_count": activity.get("near_miss_count") or 0,
        "activity_frames_evaluated_count": activity.get("frames_evaluated_count") or 0,
        "activity_candidate_frame_count": activity.get("candidate_frame_count") or 0,
        "activity_saved_candidate_count": activity.get("saved_candidate_count") or 0,
        "activity_session_duration_seconds": activity.get("session_duration_seconds")
        or 0.0,
        "activity_completed_at": activity.get("completed_at"),
        "activity_ready_for_review": _live_activity_ready_for_review(
            activity,
            quiet_seconds=quiet_seconds,
        ),
        "activity_manual_review_needed": bool(activity.get("manual_review_needed")),
        "activity_review_state": _live_activity_review_state(
            activity,
            quiet_seconds=quiet_seconds,
        ),
        "activity_subject_state": activity.get("subject_state"),
        "activity_promotion_category": activity.get("promotion_category"),
        "activity_quiet_remaining_seconds": quiet_remaining_seconds,
        "activity_best_frame_sequence": activity.get("best_frame_sequence"),
        "activity_best_score": activity.get("best_score"),
        "activity_best_changed_ratio": activity.get("best_changed_ratio"),
        "activity_best_changed_pixels": activity.get("best_changed_pixels"),
        "activity_best_total_scored_pixels": activity.get("best_total_scored_pixels"),
        "activity_effective_threshold_used": activity.get("effective_threshold_used"),
        "activity_threshold_source": activity.get("threshold_source"),
        "activity_fine_motion_applied": bool(activity.get("fine_motion_applied")),
        "activity_near_miss": bool(activity.get("near_miss")),
        "activity_cooldown_remaining_seconds": quiet_remaining_seconds,
        "activity_review_activity_created": bool(
            activity.get("review_activity_created")
        ),
        "activity_motion_evidence_id": activity.get("motion_evidence_id"),
        "activity_event_id": activity.get("event_id"),
        "activity_visit_id": activity.get("visit_id"),
        "activity_review_queue_item_id": activity.get("review_queue_item_id"),
        "notification_event": activity.get("notification_event"),
    }


def _live_activity_evaluate_fields(
    activity: dict[str, Any] | None,
    *,
    quiet_seconds: int = DEFAULT_QUIET_PERIOD_SECONDS,
) -> dict[str, Any]:
    if not activity:
        return {}
    quiet_remaining_seconds = _live_activity_quiet_remaining_seconds(
        activity,
        quiet_seconds=quiet_seconds,
    )
    return {
        "activity_session_id": activity.get("activity_session_id"),
        "activity_started_at": activity.get("started_at"),
        "activity_last_seen_at": activity.get("last_seen_at"),
        "activity_detection_count": activity.get("detection_count") or 0,
        "activity_near_miss_count": activity.get("near_miss_count") or 0,
        "activity_frames_evaluated_count": activity.get("frames_evaluated_count") or 0,
        "activity_candidate_frame_count": activity.get("candidate_frame_count") or 0,
        "activity_saved_candidate_count": activity.get("saved_candidate_count") or 0,
        "activity_session_duration_seconds": activity.get("session_duration_seconds")
        or 0.0,
        "activity_completed_at": activity.get("completed_at"),
        "activity_ready_for_review": _live_activity_ready_for_review(
            activity,
            quiet_seconds=quiet_seconds,
        ),
        "activity_review_state": _live_activity_review_state(
            activity,
            quiet_seconds=quiet_seconds,
        ),
        "activity_subject_state": activity.get("subject_state"),
        "activity_promotion_category": activity.get("promotion_category"),
        "activity_quiet_remaining_seconds": quiet_remaining_seconds,
        "activity_manual_review_needed": bool(activity.get("manual_review_needed")),
        "activity_best_frame_sequence": activity.get("best_frame_sequence"),
        "activity_best_score": activity.get("best_score"),
        "activity_best_changed_ratio": activity.get("best_changed_ratio"),
        "activity_best_changed_pixels": activity.get("best_changed_pixels"),
        "activity_best_total_scored_pixels": activity.get("best_total_scored_pixels"),
        "activity_effective_threshold_used": activity.get("effective_threshold_used"),
        "activity_threshold_source": activity.get("threshold_source"),
        "activity_fine_motion_applied": bool(activity.get("fine_motion_applied")),
        "activity_near_miss": bool(activity.get("near_miss")),
        "notification_event": activity.get("notification_event"),
    }


def _live_activity_quiet_remaining_seconds(
    activity: dict[str, Any],
    *,
    quiet_seconds: int = DEFAULT_QUIET_PERIOD_SECONDS,
) -> int | None:
    last_seen = _live_activity_datetime(activity.get("last_seen_at"))
    if last_seen is None or activity.get("review_activity_created"):
        return None
    # Zone quiet remains a nearby-return merge window; the visible close timer
    # belongs to the localized subject support.
    effective_quiet_seconds = live_camera_session.DEFAULT_ACTIVITY_LOCAL_QUIET_SECONDS
    elapsed = max(0.0, (datetime.now(UTC) - last_seen).total_seconds())
    return max(0, int(ceil(max(1, effective_quiet_seconds) - elapsed)))


def _live_activity_ready_for_review(
    activity: dict[str, Any],
    *,
    quiet_seconds: int = DEFAULT_QUIET_PERIOD_SECONDS,
) -> bool:
    if activity.get("review_activity_created"):
        return True
    if activity.get("finalized_reason") in {
        "brief_activity",
        "unpromoted_motion",
        "non_reviewable_person",
        "non_reviewable_vehicle",
    }:
        return False
    if int(activity.get("detection_count") or 0) <= 0:
        return False
    if activity.get("ready_for_review"):
        return True
    quiet_remaining_seconds = _live_activity_quiet_remaining_seconds(
        activity,
        quiet_seconds=quiet_seconds,
    )
    return quiet_remaining_seconds == 0


def _live_activity_review_state(
    activity: dict[str, Any],
    *,
    quiet_seconds: int = DEFAULT_QUIET_PERIOD_SECONDS,
) -> str:
    if activity.get("review_activity_created"):
        return "review_candidate_created"
    if activity.get("finalized_reason") == "maximum_duration":
        return "maximum_duration"
    if activity.get("finalized_reason") == "brief_activity":
        return "brief_activity_ignored"
    if activity.get("finalized_reason") == "unpromoted_motion":
        return "transient_motion"
    if activity.get("finalized_reason") in {
        "non_reviewable_person",
        "non_reviewable_vehicle",
    }:
        return "safe_category_ignored"
    if int(activity.get("detection_count") or 0) <= 0 and int(
        activity.get("near_miss_count") or 0
    ) > 0:
        return "tentative_burst"
    if _live_activity_ready_for_review(activity, quiet_seconds=quiet_seconds):
        return "ready_for_review"
    return "waiting_for_quiet"


def _live_activity_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _live_camera_session_response(
    snapshot: live_camera_session.LiveCameraSessionSnapshot | None,
    configuration: StreamLivePlaybackConfig,
    *,
    message: str | None = None,
    warnings: list[str] | None = None,
) -> LiveCameraSessionStatusResponse:
    if snapshot is None:
        return LiveCameraSessionStatusResponse(
            stream_id=configuration.stream_id,
            source_id=configuration.source_id,
            playback_kind=configuration.live_stream_type,
            status="stopped",
            max_runtime_seconds=live_camera_session.DEFAULT_MAX_RUNTIME_SECONDS,
            persistent=False,
            monitor_running=False,
            auto_create_review_candidates=False,
            auto_identify_review_candidates=False,
            auto_review_quiet_seconds=live_camera_session.DEFAULT_AUTO_REVIEW_QUIET_SECONDS,
            auto_review_min_detections=(
                live_camera_session.DEFAULT_AUTO_REVIEW_MIN_DETECTIONS
            ),
            auto_review_created_count=0,
            camera_settings=_camera_settings_from_live_config(configuration),
            message=message or "Camera session is stopped.",
            warnings=warnings or [],
        )
    return LiveCameraSessionStatusResponse(
        stream_id=snapshot.stream_id,
        source_id=snapshot.source_id,
        playback_kind=snapshot.playback_kind,
        status=snapshot.status,
        started_at=snapshot.started_at,
        last_frame_at=snapshot.last_frame_at,
        latest_frame_age_ms=snapshot.latest_frame_age_ms,
        newest_frame_age_ms=snapshot.latest_frame_age_ms,
        frame_count=snapshot.frame_count,
        clients_connected=snapshot.clients_connected,
        monitor_running=snapshot.monitor_running,
        auto_create_review_candidates=snapshot.auto_create_review_candidates,
        auto_identify_review_candidates=snapshot.auto_identify_review_candidates,
        automatic_identification_status=snapshot.automatic_identification_status,
        last_auto_identification_target_id=snapshot.last_auto_identification_target_id,
        last_auto_identification_attempt_id=snapshot.last_auto_identification_attempt_id,
        last_auto_identification_suggestion_id=snapshot.last_auto_identification_suggestion_id,
        last_auto_identification_message=snapshot.last_auto_identification_message,
        auto_review_quiet_seconds=snapshot.auto_review_quiet_seconds,
        auto_review_min_detections=snapshot.auto_review_min_detections,
        auto_review_created_count=snapshot.auto_review_created_count,
        last_auto_review_created_at=snapshot.last_auto_review_created_at,
        auto_review_last_error=snapshot.auto_review_last_error,
        last_auto_review_motion_evidence_id=snapshot.last_auto_review_motion_evidence_id,
        last_auto_review_event_id=snapshot.last_auto_review_event_id,
        last_auto_review_visit_id=snapshot.last_auto_review_visit_id,
        last_auto_review_queue_item_id=snapshot.last_auto_review_queue_item_id,
        last_motion_evaluation_at=snapshot.last_motion_evaluation_at,
        open_activity_session_count=snapshot.open_activity_session_count,
        open_activity_zone_names=snapshot.open_activity_zone_names,
        ready_activity_session_count=snapshot.ready_activity_session_count,
        latest_activity_review_queue_item_id=(
            snapshot.latest_activity_review_queue_item_id
        ),
        **_live_activity_session_status_fields(
            snapshot.current_activity_session or snapshot.last_activity,
            quiet_seconds=snapshot.auto_review_quiet_seconds,
        ),
        last_activity=snapshot.last_activity,
        last_motion_result=snapshot.last_motion_result,
        last_error=snapshot.last_error,
        stop_reason=snapshot.stop_reason,
        max_runtime_seconds=snapshot.max_runtime_seconds,
        persistent=snapshot.persistent,
        camera_settings=snapshot.camera_settings,
        message=message or _live_camera_session_message(snapshot),
        warnings=warnings or [],
    )


def _live_camera_session_message(
    snapshot: live_camera_session.LiveCameraSessionSnapshot,
) -> str:
    if snapshot.status == "running":
        return "Camera session is running. Live view, capture, and monitoring share these frames."
    if snapshot.status == "starting":
        return "Camera session is starting."
    if snapshot.status == "stopping":
        return "Camera session is stopping."
    if snapshot.status == "failed":
        return snapshot.last_error or "Camera session failed."
    if snapshot.status == "paused":
        return "Live view is paused while Observation Engine is watching this camera."
    return "Camera session is stopped."


def _camera_settings_from_live_config(
    configuration: StreamLivePlaybackConfig,
) -> dict[str, Any]:
    keys = (
        "input_format",
        "preview_video_size",
        "capture_video_size",
        "windows_video_size",
        "windows_framerate",
        "camera_video_size",
        "camera_framerate",
        "brightness",
        "contrast",
        "exposure",
        "zoom_mode",
    )
    return {
        key: value
        for key in keys
        if (value := getattr(configuration, key, None)) is not None
    }


def _camera_session_response_fields(
    snapshot: live_camera_session.LiveCameraSessionSnapshot | None,
) -> dict[str, int | str | None]:
    return {
        "camera_session_status": snapshot.status if snapshot else "stopped",
        "camera_session_frame_count": snapshot.frame_count if snapshot else 0,
        "camera_session_clients_connected": snapshot.clients_connected
        if snapshot
        else 0,
        "camera_session_latest_frame_age_ms": (
            snapshot.latest_frame_age_ms if snapshot else None
        ),
        "camera_session_runtime_limit_seconds": (
            snapshot.max_runtime_seconds if snapshot else None
        ),
    }


def _validate_live_camera_session_config(
    configuration: StreamLivePlaybackConfig,
    *,
    expected_kind: str | None = None,
) -> None:
    live_type = configuration.live_stream_type
    target_kind = expected_kind or live_type
    if target_kind == "camera_node":
        if configuration.provider_key != "camera_node":
            raise HTTPException(status_code=400, detail="Camera Node playback requires a Camera Node Source provider.")
        if live_type != "camera_node":
            raise HTTPException(status_code=400, detail="Camera Node playback configuration is incomplete.")
        if not all(
            (
                configuration.camera_node_base_address,
                configuration.camera_node_credential,
                configuration.camera_node_camera_id,
                configuration.camera_node_id,
            )
        ):
            raise HTTPException(status_code=409, detail="Pair or repair the Camera Node before opening preview or monitoring.")
        return
    if target_kind == "rtsp":
        if configuration.provider_key != "external_url":
            raise HTTPException(
                status_code=400,
                detail="RTSP bridge requires an external_url Source provider.",
            )
        if not configuration.live_stream_url:
            raise HTTPException(
                status_code=400, detail="Live stream URL is not configured."
            )
        if live_type != "rtsp":
            raise HTTPException(
                status_code=400, detail="RTSP bridge requires RTSP stream type."
            )
        if not rtsp_bridge.validate_rtsp_url(configuration.live_stream_url):
            raise HTTPException(
                status_code=400,
                detail="RTSP bridge requires an rtsp:// or rtsps:// stream URL.",
            )
        # v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.6
        # RTSPS"): the same honest refusal `_external_url_stream_playback_
        # status` already reports at status-read time, enforced again here
        # so a backend live session can never actually start a plaintext
        # ffmpeg connection for an rtsps:// URL -- see `rtsp_bridge.
        # RTSPS_TRANSPORT_SUPPORTED`'s docstring.
        if rtsp_bridge.is_rtsps_url(configuration.live_stream_url) and not rtsp_bridge.RTSPS_TRANSPORT_SUPPORTED:
            raise HTTPException(
                status_code=400,
                detail=(
                    "RTSPS (secure RTSP) is not currently supported. MockingBird will not "
                    "silently fall back to an unencrypted connection for this stream URL."
                ),
            )
        if not rtsp_bridge.is_ffmpeg_available():
            raise HTTPException(
                status_code=503,
                detail="RTSP bridge unavailable: ffmpeg not found.",
            )
        return

    if target_kind == local_camera_bridge.LOCAL_USB_STREAM_TYPE:
        if configuration.provider_key != "local_usb":
            raise HTTPException(
                status_code=400,
                detail="Local camera bridge requires a local_usb Source provider.",
            )
        if live_type != local_camera_bridge.LOCAL_USB_STREAM_TYPE:
            raise HTTPException(
                status_code=400,
                detail="Local camera bridge requires local USB playback type.",
            )
        bridge_status = local_camera_bridge.local_camera_status(
            device=configuration.local_camera_device,
            camera_format=configuration.local_camera_format,
        )
        if bridge_status == "device_missing":
            raise HTTPException(
                status_code=400,
                detail="Choose a local camera device such as /dev/video0.",
            )
        if bridge_status == "invalid_device":
            raise HTTPException(
                status_code=400,
                detail="Local camera device path must look like /dev/video0.",
            )
        if bridge_status == "unsupported_platform":
            raise HTTPException(
                status_code=400,
                detail="Local camera bridge currently supports Linux /dev/video* devices.",
            )
        if bridge_status == "ffmpeg_missing":
            raise HTTPException(
                status_code=503,
                detail="Local camera bridge unavailable: ffmpeg not found.",
            )
        return

    if target_kind == windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE:
        if configuration.provider_key != "local_usb":
            raise HTTPException(
                status_code=400,
                detail="Windows DirectShow bridge requires a local camera Source provider.",
            )
        if live_type != windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE:
            raise HTTPException(
                status_code=400,
                detail="Windows DirectShow bridge requires windows_dshow playback type.",
            )
        bridge_status = windows_camera_bridge.windows_camera_status(
            camera_name=configuration.windows_camera_name,
            ffmpeg_binary_path=configuration.windows_ffmpeg_binary_path,
        )
        if bridge_status == "camera_name_missing":
            raise HTTPException(
                status_code=400,
                detail="Choose a Windows DirectShow camera name.",
            )
        if bridge_status == "unsupported_host":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Windows DirectShow requires Windows ffmpeg.exe or running the API on Windows."
                ),
            )
        if bridge_status == "ffmpeg_missing":
            raise HTTPException(
                status_code=503,
                detail="Windows DirectShow bridge unavailable: ffmpeg not found.",
            )
        if bridge_status == "ffmpeg_failed":
            raise HTTPException(
                status_code=502,
                detail="Windows DirectShow camera unavailable or playback failed.",
            )
        return

    raise HTTPException(
        status_code=400,
        detail="Backend camera sessions require RTSP, local_usb, or windows_dshow playback.",
    )


def _managed_camera_status(
    snapshot: live_camera_session.LiveCameraSessionSnapshot | None,
) -> ManagedCameraStatus:
    if snapshot is None:
        return ManagedCameraStatus(state="stopped")
    return ManagedCameraStatus(
        state=snapshot.status,
        healthy_at=snapshot.last_frame_at,
        monitor_running=snapshot.monitor_running,
        failure_code=(
            snapshot.last_error
            if snapshot.last_error
            in CAMERA_NODE_RUNTIME_FAILURE_CODES
            else None
        ),
    )


def _supervisor_start_camera(
    candidate: DurableMonitoringCandidate,
) -> ManagedCameraStatus:
    configuration = _stream_live_playback_config_or_404(
        candidate.stream_id,
        require_active_source=True,
    )
    _validate_live_camera_session_config(configuration)
    snapshot = get_live_camera_session_manager().start(configuration)
    return _managed_camera_status(snapshot)


def _supervisor_start_monitor(
    candidate: DurableMonitoringCandidate,
) -> ManagedCameraStatus:
    evaluate_request = LiveMotionEvaluateRequest(create_review_activity=False)

    def monitor_evaluate() -> dict[str, Any]:
        # Monitoring can create review candidates only through the persisted,
        # explicitly enabled existing setting. It never creates reviewed truth.
        _maybe_auto_create_live_review_candidate(candidate.stream_id)
        result = _evaluate_live_stream_motion(
            candidate.stream_id,
            evaluate_request,
            evaluation_cadence_seconds=candidate.evaluation_interval_seconds,
        )
        _maybe_auto_create_live_review_candidate(candidate.stream_id)
        snapshot_after_evaluation = get_live_camera_session_manager().status(
            candidate.stream_id
        )
        if (
            snapshot_after_evaluation is not None
            and snapshot_after_evaluation.last_motion_result is not None
        ):
            return dict(snapshot_after_evaluation.last_motion_result)
        return result.model_dump(mode="json")

    snapshot = get_live_camera_session_manager().start_monitor(
        candidate.stream_id,
        monitor_evaluate,
        interval_seconds=candidate.evaluation_interval_seconds,
        auto_create_review_candidates=candidate.auto_create_review_candidates,
        auto_review_quiet_seconds=candidate.quiet_period_seconds,
        auto_review_min_detections=candidate.minimum_detection_count,
    )
    return _managed_camera_status(snapshot)


def _evidence_persistence_failed(error: str | None) -> bool:
    """Classify only clear managed-evidence failures; other review errors are not storage health."""

    normalized = (error or "").lower()
    return any(
        marker in normalized
        for marker in (
            "evidence persistence",
            "persist evidence",
            "storage",
            "media write",
            "write media",
            "save evidence",
        )
    )


def _supervisor_camera_status(stream_id: str) -> ManagedCameraStatus | None:
    if _live_camera_session_manager is None:
        return None
    snapshot = _live_camera_session_manager.status(stream_id)
    if snapshot is not None and snapshot.monitor_running:
        try:
            get_repository().record_stream_health_observation(
                stream_id,
                last_evidence_persisted_at=snapshot.last_auto_review_created_at,
                evidence_persistence_failed=_evidence_persistence_failed(
                    snapshot.auto_review_last_error
                ),
                now=datetime.now(UTC),
            )
        except Exception:
            # A best-effort health checkpoint must never interrupt frame handling.
            pass
    return _managed_camera_status(snapshot)


def _camera_health_with_pending_node_recovery(
    detail: CameraHealthDetailResponse,
) -> CameraHealthDetailResponse:
    """Expose a successful Node reset until the existing monitor receives one frame."""

    manager = _live_camera_session_manager
    if manager is None or not manager.monitoring_recovery_pending(detail.health.stream_id):
        return detail
    return detail.model_copy(
        update={
            "health": detail.health.model_copy(
                update={
                    "state": CameraHealthState.recovering,
                    "message": (
                        "The paired Camera Node is restoring its normal monitoring "
                        "profile after a bounded evidence capture."
                    ),
                    "failure_reason": "provider_reset_required",
                    "stale": False,
                }
            )
        }
    )


def _supervisor_stop_camera(stream_id: str, reason: str) -> None:
    if _live_camera_session_manager is not None:
        _live_camera_session_manager.stop(stream_id, reason=reason)


class CameraConfigurationApplicationService:
    """Apply one previewed camera edit while keeping runtime ownership out of routes."""

    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    async def apply(
        self,
        stream_id: str,
        payload: CameraConfigurationApplyRequest,
    ) -> CameraConfigurationApplyResponse | None:
        existing = self.repository.camera_configuration_idempotent_revision(stream_id, payload)
        if existing is not None:
            configuration = self.repository.get_camera_configuration_edit(stream_id)
            preview = self.repository.camera_configuration_preview_from_revision(stream_id, existing)
            if configuration is None or preview is None:
                return None
            return CameraConfigurationApplyResponse(
                configuration=configuration,
                preview=preview,
                revision=existing,
                idempotent=True,
                message="This camera configuration change was already applied safely.",
            )

        preview = self.repository.preview_camera_configuration(stream_id, payload)
        if preview is None:
            return None
        if preview.preview_token != payload.preview_token:
            raise CameraConfigurationConflictError("camera_configuration_preview_expired")
        if not preview.validation.can_apply:
            raise ValueError("camera_configuration_validation_required")

        runtime_stopped = False
        if preview.restart_required:
            try:
                # Existing managers own their own stop/finalization behavior. This
                # service never converts activity into product truth during a config edit.
                get_durable_monitoring_supervisor().stop_stream_for_configuration(stream_id)
                if _source_monitor_manager is not None:
                    await _source_monitor_manager.stop(stream_id)
                runtime_stopped = True
            except Exception as error:
                if preview.monitoring_desired == StreamMonitoringMode.armed:
                    get_durable_monitoring_supervisor().wake()
                raise RuntimeError("camera_configuration_runtime_stop_failed") from error

        try:
            result = self.repository.apply_camera_configuration(stream_id, payload)
        except Exception:
            # The database transaction rolls back; an explicitly requested restart
            # can resume the old local configuration through the established supervisor.
            if (
                runtime_stopped
                and preview.monitoring_desired == StreamMonitoringMode.armed
                and payload.restart_monitoring
            ):
                get_durable_monitoring_supervisor().wake()
            raise
        if result is None:
            return None

        configuration = self.repository.get_camera_configuration_edit(stream_id)
        if configuration is None:
            return None
        if result.revision.restart_requested:
            # Only an already-armed Stream with explicit confirmation may restart.
            get_durable_monitoring_supervisor().wake()
        return CameraConfigurationApplyResponse(
            configuration=configuration,
            preview=result.preview,
            revision=result.revision,
            idempotent=result.idempotent,
            message=(
                "Camera Node hardware replacement confirmed. This camera's Place, Stream, "
                "Zones, monitoring history, and reviewed truth stay attached. Review Zones "
                "-- MockingBird cannot verify the replacement camera's framing matches the "
                "original."
                if result.hardware_replacement_just_confirmed
                else "Camera configuration saved. Monitoring restart was requested through the local supervisor."
                if result.revision.restart_requested
                else "Camera configuration saved. Monitoring remains at its existing saved intent."
            ),
        )


def _live_motion_session_status(
    *,
    activity_detected: bool,
    duplicate_status: str | None,
    waiting_status: str | None = None,
) -> str:
    if waiting_status:
        return waiting_status
    if duplicate_status in {"ongoing_activity", "cooldown_suppressed"}:
        return "cooldown"
    if activity_detected:
        return "activity_detected"
    return "watching"


def _live_motion_cooldown_remaining_seconds(
    session_recommendation,
) -> int | None:
    if session_recommendation.session_status not in {
        "ongoing_activity",
        "cooldown_suppressed",
    }:
        return None
    age = session_recommendation.debug.get("existing_activity_age_seconds")
    if not isinstance(age, (int, float)):
        return None
    if session_recommendation.session_status == "ongoing_activity":
        remaining = session_recommendation.quiet_period_seconds - float(age)
    else:
        remaining = (
            session_recommendation.quiet_period_seconds
            + session_recommendation.cooldown_seconds
            - float(age)
        )
    return max(0, int(remaining + 0.999))


def _auto_motion_cells(
    frame: list[list[int | float]],
    blocked_zones: list[Zone],
) -> tuple[list[_AutoMotionCell], int]:
    height = len(frame)
    width = len(frame[0]) if height else 0
    columns, rows = _auto_region_grid_size(width=width, height=height)
    blocked_bounds = [_motion_zone_from_zone(zone) for zone in blocked_zones]

    cells: list[_AutoMotionCell] = []
    suppressed_count = 0
    for row in range(rows):
        for column in range(columns):
            left = column / columns
            top = row / rows
            right = (column + 1) / columns
            bottom = (row + 1) / rows
            candidate = _motion_zone_from_bounds(
                zone_id=f"auto-cell-r{row + 1}c{column + 1}",
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )
            if any(
                _auto_cell_blocked(candidate, blocked) for blocked in blocked_bounds
            ):
                suppressed_count += 1
                continue
            cells.append(
                _AutoMotionCell(
                    region_id=candidate.zone_id,
                    row=row,
                    column=column,
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                )
            )
    return cells, suppressed_count


def _auto_region_grid_size(*, width: int, height: int) -> tuple[int, int]:
    target_columns, target_rows = (8, 6) if width >= 32 and height >= 24 else (6, 4)
    return max(1, min(width, target_columns)), max(1, min(height, target_rows))


def _auto_cell_blocked(cell: MotionZoneInput, blocked: MotionZoneInput) -> bool:
    center_x = (cell.left + cell.right) / 2
    center_y = (cell.top + cell.bottom) / 2
    if (
        blocked.left <= center_x <= blocked.right
        and blocked.top <= center_y <= blocked.bottom
    ):
        return True

    overlap_left = max(cell.left, blocked.left)
    overlap_top = max(cell.top, blocked.top)
    overlap_right = min(cell.right, blocked.right)
    overlap_bottom = min(cell.bottom, blocked.bottom)
    if overlap_right <= overlap_left or overlap_bottom <= overlap_top:
        return False

    cell_area = (cell.right - cell.left) * (cell.bottom - cell.top)
    overlap_area = (overlap_right - overlap_left) * (overlap_bottom - overlap_top)
    return cell_area > 0 and overlap_area / cell_area >= 0.25


def _motion_zone_from_auto_cell(cell: _AutoMotionCell) -> MotionZoneInput:
    return _motion_zone_from_bounds(
        zone_id=cell.region_id,
        left=cell.left,
        top=cell.top,
        right=cell.right,
        bottom=cell.bottom,
    )


def _auto_activity_clusters(
    frame_scores: list[MotionFrameScoreResponse],
    cells: list[_AutoMotionCell],
    config: SamplerConfig,
    *,
    max_areas: int = 3,
) -> tuple[list[MotionCandidate], list[MotionActivityAreaResponse]]:
    cell_by_id = {cell.region_id: cell for cell in cells}
    cell_at = {(cell.row, cell.column): cell.region_id for cell in cells}
    triggered_by_cell: dict[str, list[tuple[int, float, int]]] = {}
    for frame_score in frame_scores:
        for score in frame_score.scores:
            if score.zone_id not in cell_by_id or not score.triggered:
                continue
            triggered_by_cell.setdefault(score.zone_id, []).append(
                (frame_score.frame_index, score.changed_ratio, score.changed_pixels)
            )

    active_ids = set(triggered_by_cell)
    visited: set[str] = set()
    clusters: list[_AutoMotionCluster] = []
    for cell_id in sorted(
        active_ids,
        key=lambda active_id: (
            cell_by_id[active_id].row,
            cell_by_id[active_id].column,
        ),
    ):
        if cell_id in visited:
            continue
        stack = [cell_id]
        cluster_ids: set[str] = set()
        while stack:
            current_id = stack.pop()
            if current_id in visited:
                continue
            visited.add(current_id)
            cluster_ids.add(current_id)
            current = cell_by_id[current_id]
            for row_offset, column_offset in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor_id = cell_at.get(
                    (current.row + row_offset, current.column + column_offset)
                )
                if neighbor_id in active_ids and neighbor_id not in visited:
                    stack.append(neighbor_id)

        cluster = _auto_motion_cluster(
            cluster_ids, cell_by_id, triggered_by_cell, config
        )
        if cluster is not None:
            clusters.append(cluster)

    strongest_clusters = sorted(
        clusters,
        key=lambda cluster: (
            cluster.peak_changed_ratio,
            len(cluster.cells),
            -cluster.start_frame_index,
        ),
        reverse=True,
    )[:max_areas]

    candidates: list[MotionCandidate] = []
    areas: list[MotionActivityAreaResponse] = []
    used_labels: set[str] = set()
    for index, cluster in enumerate(strongest_clusters, start=1):
        area_id = f"auto-area-{index}"
        label = _auto_activity_area_label(
            left=cluster.left,
            top=cluster.top,
            right=cluster.right,
            bottom=cluster.bottom,
            index=index,
            used_labels=used_labels,
        )
        used_labels.add(label)
        candidates.append(
            MotionCandidate(
                zone_id=area_id,
                start_frame_index=cluster.start_frame_index,
                end_frame_index=cluster.end_frame_index,
                best_frame_index=cluster.best_frame_index,
                peak_changed_ratio=cluster.peak_changed_ratio,
                triggered_frame_count=cluster.triggered_frame_count,
            )
        )
        areas.append(
            MotionActivityAreaResponse(
                area_id=area_id,
                label=label,
                source="auto_region",
                left=cluster.left,
                top=cluster.top,
                right=cluster.right,
                bottom=cluster.bottom,
                cell_ids=[
                    cell.region_id
                    for cell in sorted(
                        cluster.cells,
                        key=lambda cell: (cell.row, cell.column),
                    )
                ],
            )
        )
    return candidates, areas


def _auto_motion_cluster(
    cluster_ids: set[str],
    cell_by_id: dict[str, _AutoMotionCell],
    triggered_by_cell: dict[str, list[tuple[int, float, int]]],
    config: SamplerConfig,
) -> _AutoMotionCluster | None:
    events: list[tuple[int, float, int]] = []
    cells = [cell_by_id[cell_id] for cell_id in cluster_ids]
    for cell_id in cluster_ids:
        events.extend(triggered_by_cell[cell_id])

    frame_groups = _auto_frame_groups(
        sorted({frame_index for frame_index, _ratio, _pixels in events}),
        max_gap_frames=config.max_gap_frames,
    )
    ready_groups = [
        group for group in frame_groups if len(group) >= config.min_triggered_frames
    ]
    if not ready_groups:
        return None

    def group_peak(group: list[int]) -> float:
        group_frames = set(group)
        return max(
            ratio
            for frame_index, ratio, _pixels in events
            if frame_index in group_frames
        )

    best_group = max(ready_groups, key=group_peak)
    best_group_frames = set(best_group)
    best_frame_index, peak_changed_ratio, _changed_pixels = max(
        (event for event in events if event[0] in best_group_frames),
        key=lambda event: event[1],
    )
    if len(cells) == 1 and peak_changed_ratio < _auto_isolated_cell_min_ratio(
        config.min_changed_ratio
    ):
        return None

    return _AutoMotionCluster(
        cells=cells,
        start_frame_index=min(best_group),
        end_frame_index=max(best_group),
        best_frame_index=best_frame_index,
        peak_changed_ratio=peak_changed_ratio,
        triggered_frame_count=len(best_group),
        left=min(cell.left for cell in cells),
        top=min(cell.top for cell in cells),
        right=max(cell.right for cell in cells),
        bottom=max(cell.bottom for cell in cells),
    )


def _auto_frame_groups(
    frame_indices: list[int],
    *,
    max_gap_frames: int,
) -> list[list[int]]:
    groups: list[list[int]] = []
    current: list[int] = []
    for frame_index in frame_indices:
        if not current:
            current = [frame_index]
            continue
        if frame_index - current[-1] - 1 <= max_gap_frames:
            current.append(frame_index)
            continue
        groups.append(current)
        current = [frame_index]
    if current:
        groups.append(current)
    return groups


def _auto_isolated_cell_min_ratio(min_changed_ratio: float) -> float:
    return max(0.06, min(1.0, min_changed_ratio * 2.0))


def _auto_activity_area_label(
    *,
    left: float,
    top: float,
    right: float,
    bottom: float,
    index: int,
    used_labels: set[str],
) -> str:
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    vertical = (
        "Upper" if center_y < 1 / 3 else "Lower" if center_y > 2 / 3 else "Center"
    )
    horizontal = (
        "left" if center_x < 1 / 3 else "right" if center_x > 2 / 3 else "center"
    )
    label = (
        "Center activity area"
        if vertical == "Center" and horizontal == "center"
        else f"{vertical} {horizontal} activity area"
    )
    if label in used_labels:
        return f"Auto area {index}"
    return label


def _frame_asset_index(frame_index: int | None, frame_index_start: int) -> int | None:
    if frame_index is None:
        return None
    index = frame_index - frame_index_start
    if index < 0:
        return None
    return index


def _media_asset_id_for_frame(
    media_asset_ids: list[str],
    *,
    frame_index: int | None,
    frame_index_start: int,
) -> str | None:
    index = _frame_asset_index(frame_index, frame_index_start)
    if index is None or index >= len(media_asset_ids):
        return None
    return media_asset_ids[index]


def _media_timestamp_for_frame(
    frames: list[SavedMediaFrameSummary],
    *,
    frame_index: int | None,
    frame_index_start: int,
) -> str | None:
    index = _frame_asset_index(frame_index, frame_index_start)
    if index is None or index >= len(frames):
        return None
    return frames[index].created_at.isoformat()


def _media_datetime_for_frame(
    frames: list[SavedMediaFrameSummary],
    *,
    frame_index: int | None,
    frame_index_start: int,
):
    index = _frame_asset_index(frame_index, frame_index_start)
    if index is None or index >= len(frames):
        return None
    return frames[index].created_at


def _activity_session_region_id(area: MotionActivityAreaResponse | None) -> str | None:
    if area is None:
        return None
    if area.zone_id:
        return area.zone_id
    return (
        f"{area.source}:{area.label}:"
        f"{area.left:.3f}:{area.top:.3f}:{area.right:.3f}:{area.bottom:.3f}"
    )


def _motion_evidence_session_references(
    evidence_items: list[MotionEvidenceResponse],
) -> list[ExistingActivityReference]:
    references: list[ExistingActivityReference] = []
    for evidence in evidence_items:
        configured_kind = evidence.scoring_config.get("activity_region_kind")
        configured_id = evidence.scoring_config.get("activity_region_id")
        region_kind = (
            configured_kind.strip()
            if isinstance(configured_kind, str) and configured_kind.strip()
            else "zone"
            if evidence.zone_id is not None
            else None
        )
        region_id = (
            configured_id.strip()
            if isinstance(configured_id, str) and configured_id.strip()
            else evidence.zone_id
        )
        if region_kind is None or region_id is None:
            continue
        references.append(
            ExistingActivityReference(
                activity_id=evidence.id,
                source_id=evidence.source_id,
                stream_id=evidence.stream_id,
                region_kind=region_kind,
                region_id=region_id,
                created_at=evidence.created_at,
                snapshot_media_asset_id=evidence.snapshot_media_asset_id,
                status=evidence.status.value,
            )
        )
    return references


def _live_activity_region_key(
    *,
    region_kind: str,
    region_id: str | None,
    focus_zone_id: str | None,
) -> str:
    if region_id:
        return f"{region_kind}:{region_id}"
    if focus_zone_id:
        return f"focus-zone:{focus_zone_id}"
    return f"{region_kind}:unknown"


def _live_activity_best_frame_score(
    *,
    changed_ratio: float,
    changed_pixels: int | None,
    total_scored_pixels: int | None,
    fine_motion_applied: bool,
    zone_type: ZoneType | None,
    image_quality_warnings: list[str],
) -> float:
    pixel_bonus = 0.0
    if changed_pixels is not None and total_scored_pixels:
        # Pixel count helps choose a clearer frame without letting one noisy jump dominate.
        pixel_bonus = min(changed_pixels, total_scored_pixels) / total_scored_pixels
        pixel_bonus = min(pixel_bonus, 0.10)
    fine_bonus = (
        0.002
        if fine_motion_applied
        and zone_type in {ZoneType.feeder, ZoneType.birdbath, ZoneType.perch}
        else 0.0
    )
    quality_penalty = 0.001 * len(image_quality_warnings)
    return changed_ratio + pixel_bonus + fine_bonus - quality_penalty


def _ensure_live_activity_best_media_asset(
    *,
    repository: ProductRepository,
    stream: Stream,
    activity: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    media_asset_id = activity.get("best_media_asset_id")
    if media_asset_id:
        return str(media_asset_id), activity

    activity_session_id = activity.get("activity_session_id")
    if not activity_session_id:
        return None, activity

    manager = get_live_camera_session_manager()
    best_frame = manager.get_activity_best_frame(stream.id, str(activity_session_id))
    if (
        best_frame is None
        or best_frame.frame_bytes is None
        or best_frame.captured_at is None
        or best_frame.sequence is None
    ):
        return None, activity

    configuration = repository.get_stream_live_playback_config(stream.id)
    try:
        media_asset = repository.create_live_motion_frame_media_asset(
            source_id=stream.source_id,
            stream_id=stream.id,
            content=best_frame.frame_bytes,
            content_type=best_frame.content_type or "image/jpeg",
            captured_at=best_frame.captured_at,
            frame_sequence=best_frame.sequence,
            playback_type=configuration.live_stream_type if configuration else None,
            note="Saved best frame from live activity session for explicit review.",
        )
    except ValueError as error:
        raise _media_import_error(error) from error

    updated = manager.mark_activity_media_asset(
        stream.id,
        str(activity_session_id),
        media_asset.id,
    )
    if updated is None:
        return media_asset.id, {**activity, "best_media_asset_id": media_asset.id}
    return media_asset.id, updated.as_dict()


def _ensure_live_activity_high_resolution_media_assets(
    *,
    repository: ProductRepository,
    stream: Stream,
    activity: dict[str, Any],
    monitoring_media_asset_id: str,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """Persist one retained Node still and its optional derived crop at handoff.

    The full JPEG is always retained when capture succeeded.  The crop is only
    made primary after the generic geometry contract proved the mapping.  A
    failed high-resolution attempt returns no frames so the low-resolution
    activity retains its normal review path.
    """

    activity_session_id = activity.get("activity_session_id")
    if not activity_session_id:
        return [], monitoring_media_asset_id, activity
    manager = get_live_camera_session_manager()
    captured = manager.get_activity_high_resolution_evidence(
        stream.id,
        str(activity_session_id),
    )
    if not captured:
        return [], monitoring_media_asset_id, activity

    captured_at = _live_activity_datetime(captured.get("captured_at"))
    if captured_at is None:
        return [], monitoring_media_asset_id, activity
    full_width = captured.get("full_width")
    full_height = captured.get("full_height")
    if (
        not isinstance(full_width, int)
        or not isinstance(full_height, int)
        or full_width < 1
        or full_height < 1
    ):
        return [], monitoring_media_asset_id, activity
    frame_sequence = activity.get("best_frame_sequence")
    if not isinstance(frame_sequence, int) or frame_sequence < 0:
        frame_sequence = 0

    existing_full_media_asset_id = captured.get("full_media_asset_id")
    if isinstance(existing_full_media_asset_id, str):
        existing_full_asset = repository.get_media_asset(existing_full_media_asset_id)
        if existing_full_asset is not None:
            existing_crop_media_asset_id = captured.get("crop_media_asset_id")
            existing_crop_asset = (
                repository.get_media_asset(existing_crop_media_asset_id)
                if isinstance(existing_crop_media_asset_id, str)
                else None
            )
            evidence_frames = [
                {
                    "activity_session_id": str(activity_session_id),
                    "media_asset_id": existing_full_asset.id,
                    "captured_at": captured_at.astimezone(UTC).isoformat(),
                    "frame_sequence": frame_sequence,
                    "is_primary": existing_crop_asset is None,
                    "width": full_width,
                    "height": full_height,
                    "evidence_role": "high_resolution_original",
                }
            ]
            if existing_crop_asset is not None:
                evidence_frames.append(
                    {
                        "activity_session_id": str(activity_session_id),
                        "media_asset_id": existing_crop_asset.id,
                        "captured_at": captured_at.astimezone(UTC).isoformat(),
                        "frame_sequence": frame_sequence,
                        "is_primary": True,
                        "width": captured.get("crop_width"),
                        "height": captured.get("crop_height"),
                        "evidence_role": "activity_crop",
                    }
                )
            return (
                evidence_frames,
                existing_crop_asset.id
                if existing_crop_asset is not None
                else existing_full_asset.id,
                activity,
            )

    if not isinstance(captured.get("full_image"), bytes):
        return [], monitoring_media_asset_id, activity
    full_image = captured["full_image"]

    def normalized_box(value: Any) -> tuple[float, float, float, float] | None:
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            return None
        try:
            box = tuple(float(item) for item in value)
        except (TypeError, ValueError):
            return None
        return box if 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1 else None

    track_box = normalized_box(captured.get("normalized_track_box"))
    crop_box = normalized_box(captured.get("normalized_padded_crop_box"))
    common = {
        "captured_at": captured_at,
        "frame_sequence": frame_sequence,
        "content_type": "image/jpeg",
        "playback_type": "camera_node",
        "capture_profile_id": captured.get("capture_profile_id"),
        "normalized_track_box": track_box,
        "geometry_transform_id": captured.get("geometry_transform_id"),
        "trigger_id": captured.get("trigger_id"),
        "trigger_started_at": _live_activity_datetime(captured.get("trigger_started_at")),
        "capture_requested_at": _live_activity_datetime(
            captured.get("capture_requested_at")
        ),
        "evidence_captured_at": captured_at,
        "alignment_status": captured.get("alignment_status"),
        "alignment_failure_code": captured.get("alignment_failure_code"),
    }
    try:
        full_asset = repository.create_live_motion_frame_media_asset(
            source_id=stream.source_id,
            stream_id=stream.id,
            content=full_image,
            evidence_role="high_resolution_original",
            image_width=full_width,
            image_height=full_height,
            note=(
                "Saved full-resolution Camera Node still after a coherent Zone "
                "track for explicit review."
            ),
            **common,
        )
        crop_image = captured.get("crop_image")
        crop_asset = None
        if (
            isinstance(crop_image, bytes)
            and isinstance(captured.get("crop_width"), int)
            and isinstance(captured.get("crop_height"), int)
            and crop_box is not None
        ):
            crop_asset = repository.create_live_motion_frame_media_asset(
                source_id=stream.source_id,
                stream_id=stream.id,
                content=crop_image,
                parent_media_asset_id=full_asset.id,
                evidence_role="activity_crop",
                image_width=captured["crop_width"],
                image_height=captured["crop_height"],
                normalized_padded_crop_box=crop_box,
                note=(
                    "Padded activity crop derived from the retained high-resolution "
                    "Camera Node still for explicit review."
                ),
                **common,
            )
    except ValueError as error:
        raise _media_import_error(error) from error

    manager.mark_activity_high_resolution_media_assets(
        stream.id,
        str(activity_session_id),
        full_media_asset_id=full_asset.id,
        crop_media_asset_id=crop_asset.id if crop_asset is not None else None,
    )
    updated = manager.get_activity_session(stream.id, str(activity_session_id))
    evidence_frames = [
        {
            "activity_session_id": str(activity_session_id),
            "media_asset_id": full_asset.id,
            "captured_at": captured_at.astimezone(UTC).isoformat(),
            "frame_sequence": frame_sequence,
            "is_primary": crop_asset is None,
            "width": full_width,
            "height": full_height,
            "evidence_role": "high_resolution_original",
        }
    ]
    if crop_asset is not None:
        evidence_frames.append(
            {
                "activity_session_id": str(activity_session_id),
                "media_asset_id": crop_asset.id,
                "captured_at": captured_at.astimezone(UTC).isoformat(),
                "frame_sequence": frame_sequence,
                "is_primary": True,
                "width": captured["crop_width"],
                "height": captured["crop_height"],
                "evidence_role": "activity_crop",
            }
        )
    return (
        evidence_frames,
        crop_asset.id if crop_asset is not None else full_asset.id,
        updated.as_dict() if updated is not None else activity,
    )


def _ensure_live_activity_evidence_media_assets(
    *,
    repository: ProductRepository,
    stream: Stream,
    activity: dict[str, Any],
    best_media_asset_id: str,
    maximum_frames: int = live_camera_session.DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Persist the activity session's tiny frame sample without creating video."""

    activity_session_id = activity.get("activity_session_id")
    if not activity_session_id:
        return [], activity

    manager = get_live_camera_session_manager()
    policy_snapshot = activity.get("monitoring_policy")
    evidence_limit = (
        int(policy_snapshot.get("maximum_evidence_frames"))
        if isinstance(policy_snapshot, dict)
        and isinstance(policy_snapshot.get("maximum_evidence_frames"), int)
        else live_camera_session.DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES
    )
    frames = manager.get_activity_evidence_frames(
        stream.id,
        str(activity_session_id),
        max_frames=min(
            live_camera_session.DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES,
            max(1, min(evidence_limit, maximum_frames)),
        ),
    )
    if not frames:
        return [], activity

    configuration = repository.get_stream_live_playback_config(stream.id)
    persisted: list[dict[str, Any]] = []
    for frame in frames:
        media_asset_id = best_media_asset_id if frame.is_primary else frame.media_asset_id
        if media_asset_id and repository.get_media_asset(media_asset_id) is None:
            media_asset_id = None
        if media_asset_id is None:
            try:
                media_asset = repository.create_live_motion_frame_media_asset(
                    source_id=stream.source_id,
                    stream_id=stream.id,
                    content=frame.frame_bytes,
                    content_type=frame.content_type or "image/jpeg",
                    captured_at=frame.captured_at,
                    frame_sequence=frame.sequence or 0,
                    playback_type=configuration.live_stream_type if configuration else None,
                    note=(
                        "Saved bounded supporting frame from live activity session "
                        "for explicit review; this is not a video recording."
                    ),
                )
            except ValueError as error:
                raise _media_import_error(error) from error
            media_asset_id = media_asset.id
            manager.mark_activity_evidence_media_asset(
                stream.id,
                str(activity_session_id),
                frame.frame_key,
                media_asset_id,
            )

        persisted.append(
            {
                "activity_session_id": str(activity_session_id),
                "media_asset_id": media_asset_id,
                "captured_at": frame.captured_at.isoformat(),
                "frame_sequence": frame.sequence,
                "is_primary": frame.is_primary,
                "width": frame.width,
                "height": frame.height,
                "evidence_role": "tracked_best_frame" if frame.is_primary else "pretrigger",
            }
        )

    updated = manager.get_activity_session(stream.id, str(activity_session_id))
    return persisted, updated.as_dict() if updated is not None else activity


def _frame_summary_for_media_asset(
    frames: list[SavedMediaFrameSummary],
    media_asset_id: str | None,
) -> SavedMediaFrameSummary | None:
    if media_asset_id is None:
        return None
    return next(
        (frame for frame in frames if frame.media_asset_id == media_asset_id), None
    )


def _measured_activity_bounds(
    frame_planes: list[list[list[int | float]]],
    *,
    frame_index: int | None,
    frame_index_start: int,
    activity_area: MotionActivityAreaResponse | None,
    pixel_delta_threshold: float,
) -> ChangedActivityBounds | None:
    """Locate the motion itself; the activity area only selects the candidate signal."""

    if frame_index is None or activity_area is None:
        return None
    current_index = frame_index - frame_index_start
    if current_index < 1 or current_index >= len(frame_planes):
        return None
    return locate_changed_activity_bounds(
        frame_planes[current_index - 1],
        frame_planes[current_index],
        pixel_delta_threshold=pixel_delta_threshold,
        search_bounds=CropBoxNormalized(
            left=activity_area.left,
            top=activity_area.top,
            right=activity_area.right,
            bottom=activity_area.bottom,
        ),
    )


def _activity_bounds_scoring_fields(
    bounds: ChangedActivityBounds | None,
) -> dict[str, float | int | None]:
    box = bounds.box_normalized if bounds is not None else None
    return {
        "activity_left": box.left if box is not None else None,
        "activity_top": box.top if box is not None else None,
        "activity_right": box.right if box is not None else None,
        "activity_bottom": box.bottom if box is not None else None,
        "activity_changed_pixel_count": (
            bounds.changed_pixel_count if bounds is not None else None
        ),
    }


def _motion_crop_plan_response(plan: ActivityCropPlan) -> MotionCropPlanResponse:
    return MotionCropPlanResponse(
        source_media_asset_id=plan.source_media_asset_id,
        crop_box_normalized=MotionCropBoxNormalizedResponse(
            left=plan.crop_box_normalized.left,
            top=plan.crop_box_normalized.top,
            right=plan.crop_box_normalized.right,
            bottom=plan.crop_box_normalized.bottom,
        ),
        crop_box_pixels=MotionCropBoxPixelsResponse(
            left=plan.crop_box_pixels.left,
            top=plan.crop_box_pixels.top,
            right=plan.crop_box_pixels.right,
            bottom=plan.crop_box_pixels.bottom,
            width=plan.crop_box_pixels.width,
            height=plan.crop_box_pixels.height,
        ),
        crop_reason=plan.crop_reason,
        padding_ratio=plan.padding_ratio,
        is_full_frame_fallback=plan.is_full_frame_fallback,
        derived_crop_media_asset_id=plan.derived_crop_media_asset_id,
        warning=plan.warning,
    )


def _strongest_motion_summary(
    frame_scores: list[MotionFrameScoreResponse],
) -> tuple[str | None, float]:
    strongest = max(
        frame_scores,
        key=lambda score: score.strongest_changed_ratio,
        default=None,
    )
    if strongest is None:
        return None, 0.0
    return strongest.strongest_zone_id, strongest.strongest_changed_ratio


def _best_motion_candidate(candidates: list[MotionCandidate]) -> MotionCandidate | None:
    return max(
        candidates, key=lambda candidate: candidate.peak_changed_ratio, default=None
    )


def _detection_runs_for_proposals(
    repository: ProductRepository,
    proposals: list[DetectionProposal],
) -> list[DetectionRun]:
    runs: list[DetectionRun] = []
    seen_run_ids: set[str] = set()
    for proposal in proposals:
        if proposal.run_id in seen_run_ids:
            continue
        seen_run_ids.add(proposal.run_id)
        run = repository.get_detection_run(proposal.run_id)
        if run is not None:
            runs.append(run)
    return runs


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/workers/status", response_model=WorkerStatusResponse)
async def get_worker_status() -> WorkerStatusResponse:
    # Read-only lifecycle contract: no workers, providers, media, or truth writes.
    return get_repository().get_worker_status()


@app.get(
    "/api/workers/external-url-preview/dry-run",
    response_model=ExternalUrlWorkerDryRunResponse,
)
async def get_external_url_worker_dry_run_plan() -> ExternalUrlWorkerDryRunResponse:
    # Planning only: no scheduler, fetch, media, evidence, or truth writes.
    return get_repository().get_external_url_worker_dry_run_plan()


@app.post("/api/motion/evaluate-frame", response_model=MotionFrameScoreResponse)
async def evaluate_motion_frame(
    payload: MotionEvaluateFrameRequest,
) -> MotionFrameScoreResponse:
    # This evaluates caller-provided frame planes only. Future stream samplers can
    # call this contract; motion remains candidate evidence until later review.
    try:
        frame_score = score_frame_motion(
            payload.previous_frame,
            payload.current_frame,
            [_motion_zone_from_payload(zone) for zone in payload.zones],
            frame_index=payload.frame_index,
            pixel_delta_threshold=payload.pixel_delta_threshold,
            min_changed_ratio=payload.min_changed_ratio,
        )
    except ValueError as error:
        raise _motion_evaluation_error(error) from error

    return _motion_frame_score_response(frame_score)


@app.post(
    "/api/motion/extract-candidates", response_model=MotionExtractCandidatesResponse
)
async def extract_motion_candidate_windows(
    payload: MotionExtractCandidatesRequest,
) -> MotionExtractCandidatesResponse:
    # Candidate windows are evidence for later snapshot/visit creation. This
    # route does not create events, visits, review labels, exports, or species ID.
    try:
        candidates = extract_motion_candidates(
            [
                _motion_frame_score_from_payload(frame_score)
                for frame_score in payload.frame_scores
            ],
            min_triggered_frames=payload.min_triggered_frames,
            max_gap_frames=payload.max_gap_frames,
        )
    except ValueError as error:
        raise _motion_evaluation_error(error) from error

    return MotionExtractCandidatesResponse(
        candidates=[_motion_candidate_response(candidate) for candidate in candidates],
    )


@app.post(
    "/api/motion/evaluate-sequence", response_model=MotionEvaluateSequenceResponse
)
async def evaluate_motion_sequence(
    payload: MotionEvaluateSequenceRequest,
) -> MotionEvaluateSequenceResponse:
    # This contract receives already-sampled grayscale frame planes. It does no
    # media IO and creates only pending Motion Evidence when explicitly asked.
    sampler_config = SamplerConfig(
        pixel_delta_threshold=payload.pixel_delta_threshold,
        min_changed_ratio=payload.min_changed_ratio,
        min_triggered_frames=payload.min_triggered_frames,
        max_gap_frames=payload.max_gap_frames,
        frame_index_start=payload.frame_index_start,
        create_motion_evidence=payload.create_motion_evidence,
    )
    try:
        sampler_result = evaluate_sampled_frame_sequence(
            payload.frames,
            [_sampler_zone_from_payload(zone) for zone in payload.zones],
            sampler_config,
        )
    except ValueError as error:
        raise _motion_evaluation_error(error) from error

    created_evidence: list[MotionEvidenceResponse] = []
    if payload.create_motion_evidence:
        try:
            created_evidence = create_motion_evidence_from_sampler_result(
                get_repository(),
                sampler_result,
                SamplerContext(
                    source_id=payload.source_id,
                    stream_id=payload.stream_id,
                    notes=payload.notes,
                ),
                sampler_config,
            )
        except ValueError as error:
            raise _motion_evidence_error(error) from error

    return MotionEvaluateSequenceResponse(
        frame_scores=[
            _motion_frame_score_response(frame_score)
            for frame_score in sampler_result.frame_scores
        ],
        candidates=[
            _motion_candidate_response(candidate)
            for candidate in sampler_result.candidates
        ],
        created_evidence=created_evidence,
    )


@app.post(
    "/api/motion/evaluate-saved-media", response_model=MotionEvaluateSavedMediaResponse
)
async def evaluate_saved_media_motion(
    payload: MotionEvaluateSavedMediaRequest,
) -> MotionEvaluateSavedMediaResponse:
    # Saved snapshots are explicitly supplied by the user; this does no capture,
    # background source work, model inference, Event/Visit promotion, or truth writes.
    repository = get_repository()
    stream = repository.get_stream(payload.stream_id)
    if stream is None:
        raise _not_found("Stream", payload.stream_id)
    if len(payload.media_asset_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="Check motion compares two or more saved frames from the selected Stream.",
        )

    media_assets: list[MediaAsset] = []
    frames: list[SavedMediaFrame] = []
    frame_summaries: list[SavedMediaFrameSummary] = []
    for media_asset_id in payload.media_asset_ids:
        asset = repository.get_media_asset(media_asset_id)
        if asset is None:
            raise _not_found("Media asset", media_asset_id)
        if asset.stream_id != stream.id:
            raise HTTPException(
                status_code=400,
                detail="Saved snapshots for Check motion must belong to the selected Stream.",
            )
        if asset.source_id is not None and asset.source_id != stream.source_id:
            raise HTTPException(
                status_code=400,
                detail="Saved snapshots for Check motion must match the Stream Source.",
            )
        if asset.media_type != "image" or not asset.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="Check motion supports saved image snapshots only.",
            )
        media_path = repository.media_file_path(asset.id)
        if media_path is None:
            raise _not_found("Media asset", asset.id)
        try:
            frame = load_saved_image_frame_plane(
                media_path, content_type=asset.content_type
            )
        except SavedMediaFrameDecodeError as error:
            raise _saved_media_motion_error(error) from error

        media_assets.append(asset)
        frames.append(frame)
        frame_summaries.append(
            SavedMediaFrameSummary(
                media_asset_id=asset.id,
                created_at=asset.created_at,
                width=frame.width,
                height=frame.height,
            )
        )

    all_zones = repository.zones_for_stream(stream.id)
    zones_by_id = {zone.id: zone for zone in all_zones}
    requested_zone_ids = [
        zone_id for zone_id in payload.zone_ids or [] if zone_id.strip()
    ]
    candidate_zones = (
        [
            zones_by_id[zone_id]
            for zone_id in requested_zone_ids
            if zone_id in zones_by_id
        ]
        if requested_zone_ids
        else all_zones
    )
    missing_zone_ids = [
        zone_id for zone_id in requested_zone_ids if zone_id not in zones_by_id
    ]
    if missing_zone_ids:
        raise _not_found("Zone", missing_zone_ids[0])

    warnings: list[str] = []
    reviewable_zones: list[Zone] = []
    for zone in candidate_zones:
        if not zone.is_active:
            warnings.append(f"Inactive Zone skipped: {zone.name}.")
            continue
        if zone.zone_type.value in {"privacy", "ignore"}:
            warnings.append(
                f"{zone.zone_type.value.replace('_', ' ').title()} Zone skipped: {zone.name}."
            )
            continue
        reviewable_zones.append(zone)

    blocked_zones = [
        zone
        for zone in all_zones
        if zone.is_active and zone.zone_type.value in {"privacy", "ignore"}
    ]
    uses_auto_regions = not reviewable_zones
    region_source = "auto_regions" if uses_auto_regions else "user_zones"
    suppressed_auto_region_count = 0
    debug_cell_zones: list[MotionZoneInput] = []
    auto_cells: list[_AutoMotionCell] = []
    activity_areas: list[MotionActivityAreaResponse] = [
        _activity_area_from_zone(zone) for zone in reviewable_zones
    ]

    if uses_auto_regions:
        warnings.append(
            "No active reviewable Zones found; automatic activity areas were used."
        )
        # Auto cells are motion-only; future model runs belong on a finalized session best snapshot/crop.
        auto_cells, suppressed_auto_region_count = _auto_motion_cells(
            frames[0].frame,
            blocked_zones,
        )
        if suppressed_auto_region_count > 0:
            warnings.append("Privacy/ignore areas were skipped.")
        if not auto_cells:
            raise HTTPException(
                status_code=400,
                detail="Privacy/ignore Zones leave no automatic activity areas to check.",
            )
        motion_zones = [_motion_zone_from_auto_cell(cell) for cell in auto_cells]
        debug_cell_zones = motion_zones
    else:
        motion_zones = [_motion_zone_from_zone(zone) for zone in reviewable_zones]

    sampler_config = SamplerConfig(
        pixel_delta_threshold=payload.pixel_delta_threshold,
        min_changed_ratio=payload.min_changed_ratio,
        min_triggered_frames=payload.min_triggered_frames,
        max_gap_frames=payload.max_gap_frames,
        frame_index_start=payload.frame_index_start,
        create_motion_evidence=payload.create_motion_evidence,
    )
    suppressed_zone_summaries = _motion_suppressed_zone_summaries(
        [frame.frame for frame in frames],
        blocked_zones,
        sampler_config,
    )
    try:
        sampler_result = evaluate_sampled_frame_sequence(
            [frame.frame for frame in frames],
            [_sampler_zone_from_payload(zone) for zone in motion_zones],
            sampler_config,
        )
    except ValueError as error:
        raise _motion_evaluation_error(error) from error

    frame_score_responses = [
        _motion_frame_score_response(frame_score)
        for frame_score in sampler_result.frame_scores
    ]
    motion_candidates = sampler_result.candidates
    creation_skipped_reason: str | None = None
    if uses_auto_regions:
        motion_candidates, activity_areas = _auto_activity_clusters(
            frame_score_responses,
            auto_cells,
            sampler_config,
        )
        motion_zones = [_activity_area_zone_input(area) for area in activity_areas]

    candidate_responses = [
        _motion_candidate_response(candidate) for candidate in motion_candidates
    ]

    raw_strongest_zone_id, raw_strongest_changed_ratio = _strongest_motion_summary(
        frame_score_responses,
    )
    best_candidate = _best_motion_candidate(motion_candidates)
    if uses_auto_regions:
        strongest_zone_id = best_candidate.zone_id if best_candidate else None
        strongest_changed_ratio = (
            best_candidate.peak_changed_ratio
            if best_candidate
            else raw_strongest_changed_ratio
        )
    else:
        strongest_zone_id = raw_strongest_zone_id
        strongest_changed_ratio = raw_strongest_changed_ratio
    best_media_asset_id = (
        _media_asset_id_for_frame(
            payload.media_asset_ids,
            frame_index=best_candidate.best_frame_index if best_candidate else None,
            frame_index_start=payload.frame_index_start,
        )
        if best_candidate
        else None
    )
    activity_area_by_id = {area.area_id: area for area in activity_areas}
    session_activity_area = (
        activity_area_by_id.get(best_candidate.zone_id) if best_candidate else None
    )
    strongest_activity_area = session_activity_area or (
        activity_area_by_id.get(strongest_zone_id) if strongest_zone_id else None
    )
    strongest_zone = zones_by_id.get(strongest_zone_id) if strongest_zone_id else None
    strongest_zone_name = strongest_zone.name if strongest_zone else None
    strongest_zone_type = strongest_zone.zone_type if strongest_zone else None
    activity_summary = _motion_activity_summary(
        activity_detected=bool(motion_candidates),
        strongest_zone_name=strongest_zone_name,
        strongest_activity_area_label=(
            strongest_activity_area.label if strongest_activity_area else None
        ),
        uses_auto_regions=uses_auto_regions,
        suppressed_zone_summaries=suppressed_zone_summaries,
    )
    best_activity_at = _media_datetime_for_frame(
        frame_summaries,
        frame_index=best_candidate.best_frame_index if best_candidate else None,
        frame_index_start=payload.frame_index_start,
    )
    session_region_kind = "auto_area" if uses_auto_regions else "zone"
    session_region_id = _activity_session_region_id(strongest_activity_area)
    activity_region_key = _live_activity_region_key(
        region_kind=session_region_kind,
        region_id=session_region_id,
        focus_zone_id=None,
    )
    existing_session_references = _motion_evidence_session_references(
        repository.list_motion_evidence(stream_id=stream.id)
    )
    can_create_review_activity = True
    session_recommendation = recommend_activity_session(
        source_id=stream.source_id,
        stream_id=stream.id,
        region_kind=session_region_kind,
        region_id=session_region_id,
        activity_at=best_activity_at,
        activity_detected=bool(motion_candidates),
        review_activity_available=can_create_review_activity,
        best_snapshot_media_asset_id=best_media_asset_id,
        existing_activities=existing_session_references,
    )
    best_snapshot_frame = _frame_summary_for_media_asset(
        frame_summaries,
        best_media_asset_id,
    )
    measured_activity = _measured_activity_bounds(
        [frame.frame for frame in frames],
        frame_index=best_candidate.best_frame_index if best_candidate else None,
        frame_index_start=payload.frame_index_start,
        activity_area=strongest_activity_area,
        pixel_delta_threshold=payload.pixel_delta_threshold,
    )
    measured_box = measured_activity.box_normalized if measured_activity else None
    crop_plan = (
        plan_activity_crop(
            source_media_asset_id=best_media_asset_id,
            image_width=best_snapshot_frame.width,
            image_height=best_snapshot_frame.height,
            left=measured_box.left if measured_box else None,
            top=measured_box.top if measured_box else None,
            right=measured_box.right if measured_box else None,
            bottom=measured_box.bottom if measured_box else None,
            crop_reason="activity_motion",
        )
        if best_snapshot_frame is not None and best_media_asset_id is not None
        else None
    )
    created_evidence: list[MotionEvidenceResponse] = []
    if (
        payload.create_motion_evidence
        and motion_candidates
        and not session_recommendation.should_create_review_activity
    ):
        creation_skipped_reason = "activity_session_duplicate_suppressed"
        warnings.append(
            "This looks like the same recent activity, so MockingBird did not create "
            "another review item."
        )
    elif payload.create_motion_evidence and best_candidate:
        try:
            created_evidence.append(
                repository.create_motion_evidence(
                    MotionEvidenceCreateRequest(
                        source_id=stream.source_id,
                        stream_id=stream.id,
                        zone_id=(None if uses_auto_regions else best_candidate.zone_id),
                        start_frame_index=best_candidate.start_frame_index,
                        end_frame_index=best_candidate.end_frame_index,
                        best_frame_index=best_candidate.best_frame_index,
                        start_time=_media_timestamp_for_frame(
                            frame_summaries,
                            frame_index=best_candidate.start_frame_index,
                            frame_index_start=payload.frame_index_start,
                        ),
                        end_time=_media_timestamp_for_frame(
                            frame_summaries,
                            frame_index=best_candidate.end_frame_index,
                            frame_index_start=payload.frame_index_start,
                        ),
                        best_frame_time=_media_timestamp_for_frame(
                            frame_summaries,
                            frame_index=best_candidate.best_frame_index,
                            frame_index_start=payload.frame_index_start,
                        ),
                        peak_changed_ratio=best_candidate.peak_changed_ratio,
                        triggered_frame_count=best_candidate.triggered_frame_count,
                        scoring_config={
                            "source": "saved_media_motion",
                            "media_asset_count": len(media_assets),
                            "pixel_delta_threshold": payload.pixel_delta_threshold,
                            "min_changed_ratio": payload.min_changed_ratio,
                            "min_triggered_frames": payload.min_triggered_frames,
                            "max_gap_frames": payload.max_gap_frames,
                            "frame_index_start": payload.frame_index_start,
                            "attach_best_snapshot": payload.attach_best_snapshot,
                            "activity_session_status": session_recommendation.session_status,
                            "activity_session_key": session_recommendation.session_key,
                            "activity_region_kind": session_region_kind,
                            "activity_region_id": session_region_id,
                            "max_snapshots_per_session": (
                                session_recommendation.max_snapshots_per_session
                            ),
                            "best_frame_width": (
                                best_snapshot_frame.width
                                if best_snapshot_frame is not None
                                else None
                            ),
                            "best_frame_height": (
                                best_snapshot_frame.height
                                if best_snapshot_frame is not None
                                else None
                            ),
                            **_activity_bounds_scoring_fields(measured_activity),
                        },
                        snapshot_media_asset_id=(
                            best_media_asset_id
                            if payload.attach_best_snapshot
                            else None
                        ),
                        notes=payload.notes
                        or "Saved snapshot motion check created pending review activity.",
                    )
                )
            )
        except ValueError as error:
            raise _motion_evidence_error(error) from error
    return MotionEvaluateSavedMediaResponse(
        stream_id=stream.id,
        source_id=stream.source_id,
        media_asset_ids=payload.media_asset_ids,
        zones=motion_zones,
        activity_areas=activity_areas,
        region_source=region_source,
        uses_auto_regions=uses_auto_regions,
        strongest_zone_name=strongest_zone_name,
        strongest_zone_type=strongest_zone_type,
        strongest_activity_area_id=(
            strongest_activity_area.area_id if strongest_activity_area else None
        ),
        strongest_activity_area_label=(
            strongest_activity_area.label if strongest_activity_area else None
        ),
        suppressed_zone_summaries=suppressed_zone_summaries,
        suppressed_auto_region_count=suppressed_auto_region_count,
        activity_summary=activity_summary,
        can_create_review_activity=can_create_review_activity,
        review_activity_created=bool(created_evidence),
        creation_skipped_reason=creation_skipped_reason,
        session_key=session_recommendation.session_key,
        session_status=session_recommendation.session_status,
        should_create_review_activity=session_recommendation.should_create_review_activity,
        session_message=session_recommendation.message,
        existing_activity_reference=session_recommendation.existing_activity_reference,
        best_snapshot_media_asset_id=session_recommendation.best_snapshot_media_asset_id,
        best_snapshot_reason=session_recommendation.best_snapshot_reason,
        crop_plan=_motion_crop_plan_response(crop_plan) if crop_plan else None,
        quiet_period_seconds=session_recommendation.quiet_period_seconds,
        cooldown_seconds=session_recommendation.cooldown_seconds,
        max_snapshots_per_session=session_recommendation.max_snapshots_per_session,
        session_debug=session_recommendation.debug,
        debug_cell_zones=debug_cell_zones,
        frames=frame_summaries,
        frame_scores=frame_score_responses,
        candidates=candidate_responses,
        created_evidence=created_evidence,
        activity_detected=bool(motion_candidates),
        strongest_zone_id=strongest_zone_id,
        strongest_changed_ratio=strongest_changed_ratio,
        best_media_asset_id=best_media_asset_id,
        warnings=warnings,
        local_first_note=(
            "Check motion used already-saved local snapshots, keeps the full best "
            "snapshot as context, and creates reviewed labels or exports only after "
            "explicit review/correction."
        ),
    )


@app.post(
    "/api/streams/{stream_id}/live-motion/evaluate",
    response_model=LiveMotionEvaluateResponse,
)
async def evaluate_live_stream_motion(
    stream_id: str,
    payload: LiveMotionEvaluateRequest | None = None,
) -> LiveMotionEvaluateResponse:
    return _evaluate_live_stream_motion(stream_id, payload)


def _evaluate_live_stream_motion(
    stream_id: str,
    payload: LiveMotionEvaluateRequest | None = None,
    *,
    evaluation_cadence_seconds: float | None = None,
) -> LiveMotionEvaluateResponse:
    # Live monitoring reads backend session/cache frames only. It does not open
    # another camera process, create truth, or create exports.
    request = payload or LiveMotionEvaluateRequest()
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    configuration = repository.get_stream_live_playback_config(stream_id)
    session_snapshot = get_live_camera_session_manager().status(stream_id)
    active_quiet_seconds = (
        session_snapshot.auto_review_quiet_seconds
        if session_snapshot is not None
        else live_camera_session.DEFAULT_AUTO_REVIEW_QUIET_SECONDS
    )
    active_min_detections = (
        session_snapshot.auto_review_min_detections
        if session_snapshot is not None
        else live_camera_session.DEFAULT_AUTO_REVIEW_MIN_DETECTIONS
    )

    evaluated_at = datetime.now(UTC)
    cache_status = live_frame_cache.get_cache_status(
        stream.id,
        max_age_seconds=request.max_age_seconds,
        max_frames=request.max_frames,
        now=evaluated_at,
    )
    cached_frames = live_frame_cache.get_recent_frames(
        stream.id,
        max_age_seconds=request.max_age_seconds,
        max_frames=request.max_frames,
        now=evaluated_at,
    )
    common = {
        "stream_id": stream.id,
        "source_id": stream.source_id,
        "evaluated_at": evaluated_at,
        **_live_frame_cache_response_fields(cache_status),
        **_camera_session_response_fields(session_snapshot),
        "auto_create_review_candidates": (
            session_snapshot.auto_create_review_candidates
            if session_snapshot is not None
            else False
        ),
        "auto_identify_review_candidates": (
            session_snapshot.auto_identify_review_candidates
            if session_snapshot is not None
            else False
        ),
        "automatic_identification_status": (
            session_snapshot.automatic_identification_status
            if session_snapshot is not None
            else "off"
        ),
        "last_auto_identification_target_id": (
            session_snapshot.last_auto_identification_target_id
            if session_snapshot
            else None
        ),
        "last_auto_identification_attempt_id": (
            session_snapshot.last_auto_identification_attempt_id
            if session_snapshot
            else None
        ),
        "last_auto_identification_suggestion_id": (
            session_snapshot.last_auto_identification_suggestion_id
            if session_snapshot
            else None
        ),
        "last_auto_identification_message": (
            session_snapshot.last_auto_identification_message
            if session_snapshot
            else None
        ),
        "auto_review_quiet_seconds": active_quiet_seconds,
        "auto_review_min_detections": active_min_detections,
        "auto_review_created_count": (
            session_snapshot.auto_review_created_count if session_snapshot else 0
        ),
        "last_auto_review_created_at": (
            session_snapshot.last_auto_review_created_at if session_snapshot else None
        ),
        "auto_review_last_error": (
            session_snapshot.auto_review_last_error if session_snapshot else None
        ),
        "last_auto_review_motion_evidence_id": (
            session_snapshot.last_auto_review_motion_evidence_id
            if session_snapshot
            else None
        ),
        "last_auto_review_event_id": (
            session_snapshot.last_auto_review_event_id if session_snapshot else None
        ),
        "last_auto_review_visit_id": (
            session_snapshot.last_auto_review_visit_id if session_snapshot else None
        ),
        "last_auto_review_queue_item_id": (
            session_snapshot.last_auto_review_queue_item_id
            if session_snapshot
            else None
        ),
        "pixel_delta_threshold": request.pixel_delta_threshold,
        "min_changed_ratio": request.min_changed_ratio,
        "bird_sized_feeder_motion": request.bird_sized_feeder_motion,
        "creates_event": False,
        "creates_visit": False,
        "creates_truth": False,
        "creates_export": False,
        "local_first_note": (
            "Monitoring compares recent live frames from this stream. Bird Log, "
            "analytics, and exports update only after explicit review/correction."
        ),
    }
    if not cached_frames:
        has_stale_frames = stream.id in set(live_frame_cache.iter_cached_stream_ids())
        session_required = (
            configuration is not None
            and live_camera_session.is_session_supported(configuration)
            and (
                session_snapshot is None
                or session_snapshot.status not in {"starting", "running"}
            )
        )
        if session_required:
            message = "Start camera session before monitoring."
            return _recorded_live_motion_response(
                LiveMotionEvaluateResponse(
                    **common,
                    status="start_session_required",
                    session_status="waiting_for_session",
                    activity_detected=False,
                    frames_considered=0,
                    message=message,
                    last_evaluation_message=message,
                )
            )
        message = (
            "No recent live frames are available. Keep Live view open and retry."
            if has_stale_frames
            else "Open Live view and wait for live frames before monitoring."
        )
        return _recorded_live_motion_response(
            LiveMotionEvaluateResponse(
                **common,
                status="no_recent_frames"
                if has_stale_frames
                else "waiting_for_live_frames",
                session_status="no_recent_frames"
                if has_stale_frames
                else "waiting_for_frames",
                activity_detected=False,
                frames_considered=0,
                message=message,
                last_evaluation_message=message,
            )
        )
    if len(cached_frames) < 2:
        message = "Waiting for at least two recent live frames from this stream."
        return _recorded_live_motion_response(
            LiveMotionEvaluateResponse(
                **common,
                status="not_enough_frames",
                session_status="waiting_for_frames",
                activity_detected=False,
                frames_considered=len(cached_frames),
                message=message,
                last_evaluation_message=message,
            )
        )

    decoded_frames: list[SavedMediaFrame] = []
    source_luminance_frames: list[np.ndarray] = []
    decoded_cached_frames: list[live_frame_cache.LiveFrame] = []
    frame_summaries: list[LiveMotionFrameSummary] = []
    skipped_decode_count = 0
    for cached_frame in cached_frames:
        try:
            decoded = load_image_frame_plane_bytes(
                cached_frame.frame_bytes,
                content_type=cached_frame.content_type,
                max_dimension=_LIVE_TRACKED_ACTIVITY_MAX_DIMENSION,
            )
        except SavedMediaFrameDecodeError:
            # A corrupted snapshot must not take the monitor down. The next
            # valid sequence number is observed as a bounded dropped-frame gap.
            skipped_decode_count += 1
            continue
        try:
            source_luminance = _source_luminance_plane(cached_frame.frame_bytes)
        except SavedMediaFrameDecodeError:
            # The canonical decoder can supply a bounded plane for synthetic
            # or recoverable cache decoders; production JPEG/PNG frames retain
            # their source-resolution luminance plane above.
            source_luminance = np.asarray(decoded.frame, dtype=np.uint8)
            if source_luminance.ndim != 2 or source_luminance.size == 0:
                skipped_decode_count += 1
                continue
        decoded_cached_frames.append(cached_frame)
        decoded_frames.append(decoded)
        source_luminance_frames.append(source_luminance)
        frame_summaries.append(
            LiveMotionFrameSummary(
                sequence=cached_frame.sequence,
                captured_at=cached_frame.captured_at,
                width=decoded.width,
                height=decoded.height,
            )
        )
    if not decoded_frames:
        message = "Recent live frames could not be decoded for motion."
        return _recorded_live_motion_response(
            LiveMotionEvaluateResponse(
                **common,
                status="decode_failed",
                session_status="decode_failed",
                activity_detected=False,
                frames_considered=len(cached_frames),
                message=message,
                last_evaluation_message=message,
                last_error=message,
                warnings=[
                    "Live monitoring needs decodable JPEG/PNG/WebP frames from the active stream."
                ],
            )
        )
    cached_frames = decoded_cached_frames
    if len(cached_frames) < 2:
        message = "Waiting for two decodable recent live frames from this stream."
        return _recorded_live_motion_response(
            LiveMotionEvaluateResponse(
                **common,
                status="not_enough_frames",
                session_status="waiting_for_frames",
                activity_detected=False,
                frames_considered=len(cached_frames),
                message=message,
                last_evaluation_message=message,
                warnings=[
                    "One or more malformed live frames were skipped; monitoring remains active."
                ]
                if skipped_decode_count
                else [],
            )
        )

    all_zones = repository.zones_for_stream(stream.id)
    zones_by_id = {zone.id: zone for zone in all_zones}
    warnings: list[str] = []
    if skipped_decode_count:
        warnings.append(
            "One or more malformed live frames were skipped; monitoring remains active."
        )
    image_quality_warnings = _live_motion_quality_warnings(decoded_frames, all_zones)
    warnings.extend(image_quality_warnings)
    reviewable_zones: list[Zone] = []
    has_active_activity_zone = False
    for zone in all_zones:
        if not zone.is_active:
            warnings.append(f"Inactive Zone skipped: {zone.name}.")
            continue
        if zone.zone_type.value in {"privacy", "ignore"}:
            warnings.append(
                f"{zone.zone_type.value.replace('_', ' ').title()} Zone skipped: {zone.name}."
            )
            continue
        has_active_activity_zone = True
        if zone.monitoring_policy is None or not zone.monitoring_policy.monitoring_enabled:
            warnings.append(f"Monitoring disabled for Zone: {zone.name}.")
            continue
        reviewable_zones.append(zone)

    blocked_zones = [
        zone
        for zone in all_zones
        if zone.is_active and zone.zone_type.value in {"privacy", "ignore"}
    ]
    # Zone policy shapes attribution after motion; it never disables core whole-stream motion.
    uses_auto_regions = not reviewable_zones and not has_active_activity_zone
    region_source = "whole_stream"
    suppressed_auto_region_count = 0
    debug_cell_zones: list[MotionZoneInput] = []
    auto_cells: list[_AutoMotionCell] = []
    focus_zone: Zone | None = None
    if request.focus_zone_id and not uses_auto_regions:
        candidate_focus_zone = zones_by_id.get(request.focus_zone_id)
        if candidate_focus_zone in reviewable_zones:
            focus_zone = candidate_focus_zone
            reviewable_zones = [candidate_focus_zone]
        else:
            warnings.append(
                "Monitoring focus Zone was unavailable; all Zones were checked."
            )
    activity_areas: list[MotionActivityAreaResponse] = [
        _activity_area_from_zone(zone) for zone in reviewable_zones
    ]

    if uses_auto_regions:
        warnings.append(
            "No active reviewable Zones found; automatic activity areas were used."
        )
        # Auto cells are motion-only; classifier/model runs belong on a reviewed session crop.
        auto_cells, suppressed_auto_region_count = _auto_motion_cells(
            decoded_frames[0].frame,
            blocked_zones,
        )
        if suppressed_auto_region_count > 0:
            warnings.append("Privacy/ignore areas were skipped.")
        if not auto_cells:
            raise HTTPException(
                status_code=400,
                detail="Privacy/ignore Zones leave no automatic activity areas to check.",
            )
        motion_zones = [_motion_zone_from_auto_cell(cell) for cell in auto_cells]
        debug_cell_zones = motion_zones
    else:
        motion_zones = [_motion_zone_from_zone(zone) for zone in reviewable_zones]

    sampler_config = SamplerConfig(
        pixel_delta_threshold=request.pixel_delta_threshold,
        min_changed_ratio=request.min_changed_ratio,
        min_triggered_frames=request.min_triggered_frames,
        max_gap_frames=request.max_gap_frames,
        frame_index_start=cached_frames[0].sequence,
        create_motion_evidence=request.create_review_activity,
    )
    # Camera Node profiles select optional evidence capture after detector-
    # qualified activity. They never change detector admission or Zone geometry.
    suppressed_zone_summaries = _motion_suppressed_zone_summaries(
        [frame.frame for frame in decoded_frames],
        blocked_zones,
        sampler_config,
    )
    # Foreground tracking is diagnostics-only. MegaDetector observations,
    # not changed-pixel scoring, are the only durable activity admission path.
    try:
        tracked_activity = _tracked_live_motion_result(
            stream_id=stream.id,
            cached_frames=cached_frames,
            source_luminance_frames=source_luminance_frames,
            zones=all_zones,
            uses_auto_regions=uses_auto_regions,
            evaluated_at=evaluated_at,
            preset=request.detector_preset,
        )
    except ValueError:
        # Motion telemetry is deliberately non-authoritative.  A malformed
        # MOG2 analysis plane must not suppress an independently completed
        # local object-detection result for the same monitoring cache.
        tracked_activity = None
        warnings.append("Motion telemetry skipped one malformed analysis frame.")
    object_detector, object_detector_metadata = _live_object_detector_result(
        stream_id=stream.id,
        cached_frames=cached_frames,
        zones_by_id=zones_by_id,
        blocked_zones=blocked_zones,
    )
    sampler_result = _tracked_sampler_result(
        tracked_activity,
        cached_frames=cached_frames,
        zones_by_id=zones_by_id,
    )
    sequence_by_identity = {
        sha1(frame.frame_bytes).hexdigest()[:20]: frame.sequence for frame in cached_frames
    }
    object_trigger_by_candidate: dict[tuple[str, int], ObjectTrackTrigger] = {}
    object_candidates = [
        _object_track_motion_candidate(
            trigger,
            sequence_by_identity=sequence_by_identity,
            fallback_sequence=cached_frames[-1].sequence,
        )
        for trigger in object_detector.triggers
    ]
    for candidate, trigger in zip(object_candidates, object_detector.triggers, strict=True):
        object_trigger_by_candidate[(candidate.zone_id, candidate.best_frame_index)] = trigger

    used_legacy_motion_sampler = False
    if not sampler_result.candidates and not object_candidates:
        # Compatibility scoring remains bounded and diagnostics-shaped while
        # the Stream-owned foreground model is warming or unavailable.
        try:
            sampler_result = _live_motion_sampler_result(
                [frame.frame for frame in decoded_frames],
                motion_zones,
                zones_by_id,
                sampler_config,
                focus_zone_id=focus_zone.id if focus_zone else None,
                bird_sized_feeder_motion=request.bird_sized_feeder_motion,
            )
            used_legacy_motion_sampler = True
        except ValueError as error:
            raise _motion_evaluation_error(error) from error

    frame_score_responses = [
        _motion_frame_score_response(frame_score)
        for frame_score in sampler_result.frame_scores
    ]
    motion_candidates = sampler_result.candidates + object_candidates
    legacy_ignore_dominates = bool(
        used_legacy_motion_sampler
        and not object_candidates
        and suppressed_zone_summaries
        and max(
            (candidate.peak_changed_ratio for candidate in motion_candidates),
            default=0.0,
        )
        <= suppressed_zone_summaries[0].peak_changed_ratio
    )
    if legacy_ignore_dominates:
        motion_candidates = []
        warnings.append(
            "Ignored-zone motion was stronger than ordinary-zone motion; "
            "review candidate suppressed."
        )
    if uses_auto_regions:
        activity_areas = [
            MotionActivityAreaResponse(
                area_id="auto-activity-area",
                label="Automatic activity area",
                source="auto_region",
                left=0.0,
                top=0.0,
                right=1.0,
                bottom=1.0,
                zone_id=None,
            )
        ]
        motion_zones = [_activity_area_zone_input(area) for area in activity_areas]

    # Animal tracks are the only durable admission signal. Person and vehicle
    # observations remain detector telemetry; foreground motion remains bounded
    # live indication and pre-trigger context.
    animal_object_candidates = [
        candidate
        for candidate, trigger in zip(
            object_candidates, object_detector.triggers, strict=True
        )
        if trigger.label == "animal"
    ]
    best_candidate = (
        _best_motion_candidate(animal_object_candidates)
        or _best_motion_candidate(object_candidates)
        or _best_motion_candidate(sampler_result.candidates)
    )
    whole_stream_activity = bool(
        best_candidate is not None
        and best_candidate.zone_id in {"auto-activity-area", "whole-stream"}
        and not (uses_auto_regions and used_legacy_motion_sampler)
    )
    object_trigger = (
        object_trigger_by_candidate.get(
            (best_candidate.zone_id, best_candidate.best_frame_index)
        )
        if best_candidate is not None
        else None
    )
    tracked_trigger = next(
        (
            trigger
            for trigger in (tracked_activity.triggers if tracked_activity else ())
            if best_candidate is not None
            and trigger.zone_id == best_candidate.zone_id
            and (
                trigger.best_frame_identity is None
                or sequence_by_identity.get(trigger.best_frame_identity)
                == best_candidate.best_frame_index
            )
        ),
        None,
    )
    # A track is admitted only on its fresh immutable trigger. A later
    # stationary snapshot remains telemetry and cannot keep local support alive
    # or reopen a finalized Visit for the same track generation.
    object_promotion_trigger = (
        object_trigger
        if object_trigger is not None and object_trigger.label == "animal"
        else None
    )
    supporting_object_track = next(
        (
            track
            for track in object_detector.tracks
            if object_promotion_trigger is not None
            and track.track_generation_id
            == object_promotion_trigger.track_generation_id
        ),
        None,
    )
    object_track_generation_id = (
        object_promotion_trigger.track_generation_id
        if object_promotion_trigger is not None
        else None
    )
    motion_track_generation_id = (
        tracked_trigger.track_generation_id if tracked_trigger is not None else None
    )
    activity_track_generation_id = object_track_generation_id or motion_track_generation_id
    animal_promotion_trigger = (
        object_promotion_trigger
        if object_promotion_trigger is not None
        and object_promotion_trigger.label == "animal"
        else None
    )
    strongest_suppressed_zone = (
        suppressed_zone_summaries[0] if suppressed_zone_summaries else None
    )
    # Privacy and Ignore masks were already applied before components reached
    # tracking.  Legacy ratio summaries remain diagnostic-only and cannot
    # suppress a coherent ordinary-Zone track.
    suppressed_strongest_motion = legacy_ignore_dominates

    candidate_responses = [
        _motion_candidate_response(candidate) for candidate in motion_candidates
    ]
    raw_strongest_zone_id, raw_strongest_changed_ratio = _strongest_motion_summary(
        frame_score_responses,
    )
    if object_promotion_trigger is not None:
        strongest_zone_id = (
            object_promotion_trigger.zone_id
            if object_promotion_trigger.zone_id in zones_by_id
            else None
        )
        strongest_changed_ratio = object_promotion_trigger.score
    elif whole_stream_activity:
        strongest_zone_id = None
        strongest_changed_ratio = best_candidate.peak_changed_ratio if best_candidate else 0.0
    elif uses_auto_regions:
        strongest_zone_id = best_candidate.zone_id if best_candidate else None
        strongest_changed_ratio = (
            best_candidate.peak_changed_ratio
            if best_candidate
            else raw_strongest_changed_ratio
        )
    elif suppressed_strongest_motion and strongest_suppressed_zone is not None:
        strongest_zone_id = strongest_suppressed_zone.zone_id
        strongest_changed_ratio = strongest_suppressed_zone.peak_changed_ratio
    else:
        strongest_zone_id = raw_strongest_zone_id
        strongest_changed_ratio = raw_strongest_changed_ratio

    activity_area_by_id = {area.area_id: area for area in activity_areas}
    strongest_activity_area = (
        MotionActivityAreaResponse(
            area_id="whole-stream-activity",
            label="General activity",
            source="whole_stream",
            left=0.0,
            top=0.0,
            right=1.0,
            bottom=1.0,
            zone_id=None,
        )
        if whole_stream_activity
        else (
            activity_areas[0]
            if uses_auto_regions and best_candidate
            else (
                activity_area_by_id.get(best_candidate.zone_id)
                if best_candidate
                else (
                    activity_area_by_id.get(strongest_zone_id)
                    if strongest_zone_id
                    else None
                )
            )
        )
    )
    strongest_zone = zones_by_id.get(strongest_zone_id) if strongest_zone_id else None
    strongest_zone_name = strongest_zone.name if strongest_zone else None
    strongest_zone_type = strongest_zone.zone_type if strongest_zone else None
    strongest_focus_applied = (
        focus_zone is not None and strongest_zone_id == focus_zone.id
    )
    strongest_scoring_policy = (
        _live_motion_zone_scoring_policy(
            zone_type=strongest_zone_type,
            zone_policy=(strongest_zone.monitoring_policy if strongest_zone else None),
            base_min_changed_ratio=request.min_changed_ratio,
            pixel_delta_threshold=request.pixel_delta_threshold,
            focus_applied=strongest_focus_applied,
            bird_sized_feeder_motion=request.bird_sized_feeder_motion,
        )
        if strongest_zone_id
        else None
    )
    strongest_zone_min_changed_ratio = (
        strongest_scoring_policy.min_changed_ratio
        if strongest_scoring_policy is not None and object_promotion_trigger is None
        else None
    )
    effective_threshold_used = (
        strongest_scoring_policy.min_changed_ratio
        if strongest_scoring_policy is not None and object_promotion_trigger is None
        else None
    )
    strongest_score, strongest_score_frame_index = _strongest_live_motion_score(
        frame_score_responses,
        strongest_zone_id=strongest_zone_id,
    )
    activity_detected = bool(motion_candidates)
    margin_to_threshold = _live_motion_margin_to_threshold(
        strongest_changed_ratio=strongest_changed_ratio,
        effective_threshold=effective_threshold_used,
    )
    near_miss = _live_motion_near_miss(
        activity_detected=activity_detected,
        strongest_score=strongest_score,
        effective_threshold=effective_threshold_used,
        scoring_policy=(
            strongest_scoring_policy if object_promotion_trigger is None else None
        ),
    )
    diagnostic_message = _live_motion_diagnostic_message(
        activity_detected=activity_detected,
        near_miss=near_miss,
        strongest_zone_name=strongest_zone_name,
        strongest_zone_type=strongest_zone_type,
        strongest_changed_ratio=strongest_changed_ratio,
        effective_threshold=effective_threshold_used,
        fine_motion_applied=(
            strongest_scoring_policy.fine_motion_applied
            if strongest_scoring_policy is not None and object_promotion_trigger is None
            else False
        ),
    )
    warnings.extend(
        _live_motion_zone_context_warnings(
            strongest_zone=strongest_zone,
            reviewable_zones=reviewable_zones,
        )
    )
    diagnostic_frame_start_sequence, diagnostic_frame_end_sequence = (
        _live_motion_pair_sequences(cached_frames, strongest_score_frame_index)
    )
    activity_summary = _motion_activity_summary(
        activity_detected=bool(motion_candidates),
        strongest_zone_name=strongest_zone_name,
        strongest_activity_area_label=(
            strongest_activity_area.label if strongest_activity_area else None
        ),
        uses_auto_regions=uses_auto_regions,
        suppressed_zone_summaries=suppressed_zone_summaries,
    )
    activity_frame_index = (
        best_candidate.best_frame_index
        if best_candidate is not None
        else strongest_score_frame_index
    )
    promoted_animal_region = (
        _object_trigger_region(
            animal_promotion_trigger,
            source_width=(
                tracked_activity.telemetry.source_width
                if tracked_activity
                else frame_summaries[-1].width
            ),
            source_height=(
                tracked_activity.telemetry.source_height
                if tracked_activity
                else frame_summaries[-1].height
            ),
        )
        if animal_promotion_trigger is not None
        else None
    )
    tracked_best_region = (
        _object_trigger_region(
            object_promotion_trigger,
            source_width=(tracked_activity.telemetry.source_width if tracked_activity else frame_summaries[-1].width),
            source_height=(tracked_activity.telemetry.source_height if tracked_activity else frame_summaries[-1].height),
        )
        if object_promotion_trigger is not None
        else _tracked_trigger_region(
            tracked_trigger,
            source_width=(tracked_activity.telemetry.source_width if tracked_activity else frame_summaries[-1].width),
            source_height=(tracked_activity.telemetry.source_height if tracked_activity else frame_summaries[-1].height),
        )
        if tracked_trigger is not None
        else None
    )
    measured_activity = (
        ChangedActivityBounds(
            box_normalized=CropBoxNormalized(
                left=tracked_best_region.left,
                top=tracked_best_region.top,
                right=tracked_best_region.right,
                bottom=tracked_best_region.bottom,
            ),
            changed_pixel_count=tracked_best_region.pixel_area,
        )
        if tracked_best_region is not None
        else _measured_activity_bounds(
            [frame.frame for frame in decoded_frames],
            frame_index=(
                best_candidate.best_frame_index if best_candidate is not None else None
            ),
            frame_index_start=cached_frames[0].sequence,
            activity_area=strongest_activity_area,
            pixel_delta_threshold=request.pixel_delta_threshold,
        )
    )
    best_live_frame = (
        next(
            (
                cached_frame
                for cached_frame in cached_frames
                if sha1(cached_frame.frame_bytes).hexdigest()[:20]
                == object_promotion_trigger.frame_identity
            ),
            None,
        )
        if object_promotion_trigger is not None
        else (
            next(
                (
                    cached_frame
                    for cached_frame in cached_frames
                    if cached_frame.sequence == best_candidate.best_frame_index
                ),
                None,
            )
            if best_candidate
            else None
        )
    )
    best_live_frame_summary = (
        next(
            (
                frame_summary
                for frame_summary in frame_summaries
                if best_live_frame is not None
                and frame_summary.sequence == best_live_frame.sequence
            ),
            None,
        )
        if best_live_frame is not None
        else None
    )
    burst_live_frame = best_live_frame
    burst_live_frame_summary = best_live_frame_summary
    if burst_live_frame is None and strongest_score_frame_index is not None:
        burst_live_frame = next(
            (
                cached_frame
                for cached_frame in cached_frames
                if cached_frame.sequence == strongest_score_frame_index
            ),
            None,
        )
        burst_live_frame_summary = next(
            (
                frame_summary
                for frame_summary in frame_summaries
                if burst_live_frame is not None
                and frame_summary.sequence == burst_live_frame.sequence
            ),
            None,
        )
    strongest_frame_start_sequence, strongest_frame_end_sequence = (
        _live_motion_pair_sequences(
            cached_frames,
            best_candidate.best_frame_index if best_candidate else None,
        )
    )
    session_region_kind = (
        "stream"
        if whole_stream_activity
        or (object_promotion_trigger is not None and strongest_zone is None)
        else "auto_area"
        if uses_auto_regions
        else "zone"
    )
    session_region_id = (
        "whole-frame"
        if whole_stream_activity
        else _activity_session_region_id(strongest_activity_area)
    )
    existing_session_references = _motion_evidence_session_references(
        repository.list_motion_evidence(stream_id=stream.id)
    )
    activity_region_key = _live_activity_region_key(
        region_kind=session_region_kind,
        region_id=session_region_id,
        focus_zone_id=focus_zone.id if focus_zone else None,
    )
    if activity_track_generation_id is not None:
        activity_region_key = f"{activity_region_key}|track:{activity_track_generation_id}"
    has_reviewable_live_activity = object_promotion_trigger is not None
    strongest_zone_policy = strongest_zone.monitoring_policy if strongest_zone else None
    session_activity_signal = (
        burst_live_frame is not None and object_promotion_trigger is not None
    )
    session_recommendation = recommend_activity_session(
        source_id=stream.source_id,
        stream_id=stream.id,
        region_kind=session_region_kind,
        region_id=session_region_id,
        activity_at=best_live_frame.captured_at if best_live_frame else None,
        activity_detected=object_promotion_trigger is not None,
        review_activity_available=has_reviewable_live_activity,
        best_snapshot_media_asset_id=None,
        existing_activities=existing_session_references,
    )
    detector_evidence_payload = _tracked_activity_evidence_payload(
        tracked_activity, object_detector
    )
    if isinstance(detector_evidence_payload.get("object_detector"), dict):
        detector_evidence_payload["object_detector"]["input"] = {
            "zone_id": object_detector_metadata["zone_id"],
            "zone_source_crop_width": object_detector_metadata["source_width"],
            "zone_source_crop_height": object_detector_metadata["source_height"],
            "input_width": object_detector_metadata["input_width"],
            "input_height": object_detector_metadata["input_height"],
        }
    live_activity_session: dict[str, Any] | None = None
    live_activity_session_active = (
        session_snapshot is not None
        and session_snapshot.status in {"starting", "running"}
        and session_activity_signal
    )
    if live_activity_session_active:
        burst_start_sequence, burst_end_sequence = (
            (strongest_frame_start_sequence, strongest_frame_end_sequence)
            if best_candidate is not None
            else (diagnostic_frame_start_sequence, diagnostic_frame_end_sequence)
        )
        activity_snapshot = get_live_camera_session_manager().record_activity_detection(
            stream.id,
            {
                "region_key": activity_region_key,
                "region_kind": session_region_kind,
                "region_id": session_region_id,
                "zone_id": (
                    None
                    if whole_stream_activity or uses_auto_regions
                    else strongest_zone_id
                ),
                "zone_name": strongest_zone_name
                or (strongest_activity_area.label if strongest_activity_area else None),
                "zone_type": strongest_zone_type.value
                if strongest_zone_type is not None
                else None,
                "last_seen_at": burst_live_frame.captured_at,
                "activity_detected": object_promotion_trigger is not None,
                "frames_evaluated_count": len(cached_frames),
                "start_frame_sequence": burst_start_sequence,
                "end_frame_sequence": burst_end_sequence,
                "best_frame_sequence": burst_live_frame.sequence,
                "best_frame_captured_at": burst_live_frame.captured_at,
                "best_frame_width": (
                    burst_live_frame_summary.width if burst_live_frame_summary else None
                ),
                "best_frame_height": (
                    burst_live_frame_summary.height
                    if burst_live_frame_summary
                    else None
                ),
                "best_score": _live_activity_best_frame_score(
                    changed_ratio=strongest_changed_ratio,
                    changed_pixels=strongest_score.changed_pixels
                    if strongest_score
                    else None,
                    total_scored_pixels=strongest_score.total_pixels
                    if strongest_score
                    else None,
                    fine_motion_applied=(
                        strongest_scoring_policy.fine_motion_applied
                        if strongest_scoring_policy is not None
                        else False
                    ),
                    zone_type=strongest_zone_type,
                    image_quality_warnings=image_quality_warnings,
                ),
                "changed_ratio": strongest_changed_ratio,
                "changed_pixels": strongest_score.changed_pixels
                if strongest_score
                else None,
                "total_scored_pixels": strongest_score.total_pixels
                if strongest_score
                else None,
                "effective_threshold_used": effective_threshold_used,
                "threshold_source": (
                    "object_verified"
                    if object_promotion_trigger is not None
                    else (
                        strongest_scoring_policy.threshold_source
                        if strongest_scoring_policy is not None
                        else "tracked_region"
                    )
                ),
                "track_generation_id": activity_track_generation_id,
                "promotion_category": (
                    object_promotion_trigger.label
                    if object_promotion_trigger is not None
                    else None
                ),
                "support_box": (
                    [
                        tracked_best_region.left,
                        tracked_best_region.top,
                        tracked_best_region.right,
                        tracked_best_region.bottom,
                    ]
                    if tracked_best_region is not None
                    else None
                ),
                "fine_motion_applied": (
                    strongest_scoring_policy.fine_motion_applied
                    if strongest_scoring_policy is not None
                    else False
                ),
                "bird_sized_feeder_motion": request.bird_sized_feeder_motion,
                "detector_evidence": detector_evidence_payload,
                "monitoring_policy": (
                    strongest_zone_policy.model_dump(mode="json")
                    if strongest_zone_policy is not None
                    else None
                ),
                "image_quality_warnings": image_quality_warnings,
                "near_miss": near_miss,
                "margin_to_threshold": margin_to_threshold,
                **_activity_bounds_scoring_fields(measured_activity),
            },
            frame_bytes=burst_live_frame.frame_bytes,
            frame_content_type=burst_live_frame.content_type,
            quiet_window_seconds=(
                strongest_zone_policy.quiet_period_seconds
                if strongest_zone_policy is not None
                else active_quiet_seconds
            ),
        )
        manager = get_live_camera_session_manager()
        if activity_snapshot is not None and supporting_object_track is not None:
            support_snapshot = manager.record_activity_track_support(
                stream.id,
                supporting_object_track.track_generation_id,
                observed_at=supporting_object_track.last_seen_at,
                detector_evidence={
                    **detector_evidence_payload,
                    "current_track": {
                        "track_id": supporting_object_track.track_id,
                        "track_generation_id": supporting_object_track.track_generation_id,
                        "zone_id": supporting_object_track.zone_id,
                        "class": supporting_object_track.label,
                        "score": supporting_object_track.score,
                        "box": list(supporting_object_track.box),
                        "frame_identity": supporting_object_track.frame_identity,
                        "captured_at": supporting_object_track.last_seen_at.isoformat(),
                    },
                },
                support_box=supporting_object_track.box,
                promotion_category=supporting_object_track.label,
            )
            if support_snapshot is not None:
                activity_snapshot = support_snapshot
        if activity_snapshot is not None and object_promotion_trigger is not None:
            pretrigger_frames = _object_pretrigger_live_frames(
                object_promotion_trigger,
                cached_frames=cached_frames,
                frame_summaries=frame_summaries,
            )
            if pretrigger_frames:
                activity_snapshot = (
                    get_live_camera_session_manager().record_activity_pretrigger_frames(
                        stream.id,
                        activity_snapshot.activity_session_id,
                        pretrigger_frames,
                    )
                    or activity_snapshot
                )
            if (
                activity_snapshot.promotion_category == "animal"
                and animal_promotion_trigger is not None
                and promoted_animal_region is not None
                and manager.get_activity_high_resolution_evidence(
                    stream.id,
                    activity_snapshot.activity_session_id,
                )
                is None
            ):
                capture_trigger = animal_promotion_trigger
                capture_track_generation_id = capture_trigger.track_generation_id
                if capture_track_generation_id is not None:
                    capture_zone = zones_by_id.get(capture_trigger.zone_id)
                    capture_box = list(capture_trigger.box)
                    qualifying_frame_identity = capture_trigger.frame_identity
                    claim = manager.claim_activity_high_resolution_capture(
                        stream.id,
                        activity_snapshot.activity_session_id,
                        {
                            "zone_id": capture_trigger.zone_id,
                            "track_generation_id": capture_track_generation_id,
                            "qualifying_frame_identity": qualifying_frame_identity,
                            "detector_name": "megadetector",
                            "detector_class": "animal",
                            "detector_score": capture_trigger.score,
                            "normalized_track_box": capture_box,
                            "monitoring_width": frame_summaries[-1].width,
                            "monitoring_height": frame_summaries[-1].height,
                            "zone_geometry": (
                                [[point.x, point.y] for point in capture_zone.polygon]
                                if capture_zone is not None
                                else []
                            ),
                            **_high_resolution_capture_claim_profile_lineage(
                                configuration
                            ),
                        },
                    )
                    if claim is not None:
                        captured_evidence = _capture_high_resolution_activity_evidence(
                            configuration=configuration,
                            region=promoted_animal_region,
                            trigger_track_id=capture_trigger.track_id,
                            trigger_at=capture_trigger.captured_at,
                            capture_claim=claim,
                        ) or {
                            **claim,
                            "capture_failure_code": "capture_unavailable",
                        }
                        captured_evidence["track_generation_id"] = (
                            capture_track_generation_id
                        )
                        if (
                            captured_evidence.get("monitoring_recovery")
                            == "reset_required"
                        ):
                            manager.mark_monitoring_recovery_pending(stream.id)
                        completed_capture = (
                            manager.complete_activity_high_resolution_capture(
                                stream.id,
                                activity_snapshot.activity_session_id,
                                str(claim["capture_claim_id"]),
                                captured_evidence,
                            )
                        )
                        if completed_capture is not None:
                            activity_snapshot = completed_capture
                            qualifying_monitoring_frame = next(
                                (
                                    frame
                                    for frame in cached_frames
                                    if sha1(frame.frame_bytes).hexdigest()[:20]
                                    == qualifying_frame_identity
                                ),
                                None,
                            )
                            qualifying_monitoring_summary = next(
                                (
                                    summary
                                    for summary in frame_summaries
                                    if qualifying_monitoring_frame is not None
                                    and summary.sequence
                                    == qualifying_monitoring_frame.sequence
                                ),
                                None,
                            )
                            completed_claim = (
                                completed_capture.high_resolution_capture_claim
                            )
                            if (
                                qualifying_monitoring_frame is not None
                                and qualifying_monitoring_summary is not None
                                and completed_claim is not None
                            ):
                                activity_diagnostic_export_from_capture(
                                    capture_claim=completed_claim,
                                    captured_evidence=captured_evidence,
                                    qualifying_monitoring_jpeg=(
                                        qualifying_monitoring_frame.frame_bytes
                                    ),
                                    qualifying_monitoring_width=(
                                        qualifying_monitoring_summary.width
                                    ),
                                    qualifying_monitoring_height=(
                                        qualifying_monitoring_summary.height
                                    ),
                                )
        live_activity_session = (
            activity_snapshot.as_dict() if activity_snapshot is not None else None
        )
    best_media_asset_id: str | None = None
    visit_evidence_frames: list[dict[str, Any]] = []
    if live_activity_session is not None:
        best_media_asset_id = live_activity_session.get("best_media_asset_id")
    promoted_animal_activity = bool(
        (live_activity_session or {}).get("promotion_category") == "animal"
        or animal_promotion_trigger is not None
    )
    should_save_best_frame = (
        bool(best_candidate)
        and best_live_frame is not None
        and promoted_animal_activity
        and (request.save_best_frame or request.create_review_activity)
        and live_activity_session is None
        and session_recommendation.session_status == "new_activity"
    )
    if should_save_best_frame:
        configuration = repository.get_stream_live_playback_config(stream.id)
        try:
            media_asset = repository.create_live_motion_frame_media_asset(
                source_id=stream.source_id,
                stream_id=stream.id,
                content=best_live_frame.frame_bytes,
                content_type=best_live_frame.content_type,
                captured_at=best_live_frame.captured_at,
                frame_sequence=best_live_frame.sequence,
                playback_type=configuration.live_stream_type if configuration else None,
                note="Saved from live monitoring activity detection.",
            )
        except ValueError as error:
            raise _media_import_error(error) from error
        best_media_asset_id = media_asset.id
    if (
        request.create_review_activity
        and promoted_animal_activity
        and live_activity_session is not None
    ):
        best_media_asset_id, live_activity_session = (
            _ensure_live_activity_best_media_asset(
                repository=repository,
                stream=stream,
                activity=live_activity_session,
            )
        )
        if best_media_asset_id is not None:
            high_resolution_frames, preferred_media_asset_id, live_activity_session = (
                _ensure_live_activity_high_resolution_media_assets(
                    repository=repository,
                    stream=stream,
                    activity=live_activity_session,
                    monitoring_media_asset_id=str(best_media_asset_id),
                )
            )
            # The high-resolution original and its valid crop consume part of
            # the existing four-frame Visit budget rather than expanding it.
            evidence_frame_limit = max(
                1,
                live_camera_session.DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES
                - len(high_resolution_frames),
            )
            # The short ring remains memory-only until this explicit reviewable
            # Visit handoff.  Persist at most the existing evidence cap, never
            # an unbounded frame sequence or a recording.
            monitoring_evidence_frames, live_activity_session = (
                _ensure_live_activity_evidence_media_assets(
                    repository=repository,
                    stream=stream,
                    activity=live_activity_session,
                    best_media_asset_id=best_media_asset_id,
                    maximum_frames=evidence_frame_limit,
                )
            )
            # A valid high-resolution crop (or its aligned full still) is the
            # sole primary item.  If capture failed, preserve the normal
            # monitoring-frame primary instead of producing an invalid
            # no-primary evidence set.
            if high_resolution_frames:
                for frame in monitoring_evidence_frames:
                    frame["is_primary"] = False
            visit_evidence_frames = high_resolution_frames + monitoring_evidence_frames
            best_media_asset_id = preferred_media_asset_id
    live_activity_review_created = bool(
        live_activity_session and live_activity_session.get("review_activity_created")
    )
    can_create_review_activity = (
        promoted_animal_activity
        and has_reviewable_live_activity
        and not live_activity_review_created
        and (
            live_activity_session is not None
            or (
                best_media_asset_id is not None
                and session_recommendation.session_status == "new_activity"
            )
        )
    )
    review_activity_available = (
        can_create_review_activity
        and session_recommendation.should_create_review_activity
    )
    if live_activity_session is not None and can_create_review_activity:
        review_activity_available = True

    created_evidence: list[MotionEvidenceResponse] = []
    review_motion_evidence: MotionEvidenceResponse | None = None
    review_event_id: str | None = None
    review_visit_id: str | None = None
    review_activity_created = False
    review_activity_reused = False
    review_activity_suggestion: SpeciesSuggestionResponse | None = None
    legacy_activity_suggestion = (
        _live_activity_suggestion_for_zone(
            strongest_zone_type,
            strongest_zone_name,
        )
        if used_legacy_motion_sampler
        else None
    )

    def record_object_admission_promotion(
        *,
        event_id: str | None = None,
        visit_id: str | None = None,
        error_category: str | None = None,
    ) -> None:
        get_live_object_detector_manager().record_admission_promotion(
            stream_id=stream.id,
            track_generation_id=object_track_generation_id,
            event_id=event_id,
            visit_id=visit_id,
            error_category=error_category,
        )

    def live_motion_promotion_payload() -> MotionEvidencePromoteRequest:
        area_label = strongest_activity_area.label if strongest_activity_area else None
        event_title = (
            f"Live motion activity in {area_label}"
            if area_label
            else "Live motion activity"
        )
        return MotionEvidencePromoteRequest(
            event_title=event_title,
            visit_label_hint=(
                legacy_activity_suggestion.label
                if legacy_activity_suggestion is not None
                else "unknown_animal"
            ),
            notes=request.notes
            or "Live stream motion monitor created an uncertain needs-review activity.",
            create_event=True,
            create_visit=True,
            attach_snapshot_media_asset_id=best_media_asset_id,
        )

    if (
        request.create_review_activity
        and promoted_animal_activity
        and live_activity_session is not None
        and live_activity_session.get("motion_evidence_id")
    ):
        existing_evidence = repository.get_motion_evidence(
            str(live_activity_session["motion_evidence_id"])
        )
        if existing_evidence is not None:
            review_motion_evidence = existing_evidence
            review_event_id = existing_evidence.promoted_event_id
            review_visit_id = existing_evidence.promoted_visit_id
            review_activity_reused = True
            review_activity_available = False
    elif (
        request.create_review_activity
        and promoted_animal_activity
        and motion_candidates
        and not session_recommendation.should_create_review_activity
    ):
        existing_evidence = (
            repository.get_motion_evidence(
                session_recommendation.existing_activity_reference,
            )
            if session_recommendation.existing_activity_reference
            else None
        )
        if (
            existing_evidence
            and existing_evidence.status == MotionEvidenceStatus.pending
        ):
            try:
                promoted = repository.promote_motion_evidence(
                    existing_evidence.id,
                    live_motion_promotion_payload(),
                )
            except ValueError as error:
                record_object_admission_promotion(
                    error_category="durable_promotion_failed"
                )
                raise _motion_evidence_error(error) from error
            if promoted is None:
                record_object_admission_promotion(
                    error_category="durable_promotion_unavailable"
                )
            else:
                record_object_admission_promotion(
                    event_id=promoted.event_id, visit_id=promoted.visit_id
                )
                review_motion_evidence = promoted.evidence
                review_event_id = promoted.event_id
                review_visit_id = promoted.visit_id
                created_evidence.append(promoted.evidence)
                review_activity_created = True
                review_activity_reused = True
        elif existing_evidence:
            review_motion_evidence = existing_evidence
            review_event_id = existing_evidence.promoted_event_id
            review_visit_id = existing_evidence.promoted_visit_id
            review_activity_reused = True

        if review_motion_evidence is None:
            warnings.append(
                "This looks like the same recent activity, so MockingBird did not create "
                "another review item."
            )
    elif (
        request.create_review_activity
        and promoted_animal_activity
        and best_candidate
        and best_live_frame
    ):
        try:
            pending_evidence = repository.create_motion_evidence(
                MotionEvidenceCreateRequest(
                    source_id=stream.source_id,
                    stream_id=stream.id,
                    zone_id=(
                        None
                        if whole_stream_activity or uses_auto_regions
                        else best_candidate.zone_id
                    ),
                    start_frame_index=best_candidate.start_frame_index,
                    end_frame_index=best_candidate.end_frame_index,
                    best_frame_index=best_candidate.best_frame_index,
                    start_time=_live_frame_timestamp(
                        cached_frames,
                        best_candidate.start_frame_index,
                    ),
                    end_time=_live_frame_timestamp(
                        cached_frames,
                        best_candidate.end_frame_index,
                    ),
                    best_frame_time=best_live_frame.captured_at.isoformat(),
                    peak_changed_ratio=best_candidate.peak_changed_ratio,
                    triggered_frame_count=best_candidate.triggered_frame_count,
                    scoring_config={
                        "source": (
                            "live_stream_motion_session_activity"
                            if live_activity_session is not None
                            else "live_stream_motion"
                        ),
                        **(
                            {
                                "activity_session_id": str(
                                    live_activity_session["activity_session_id"]
                                ),
                                "activity_started_at": str(
                                    live_activity_session.get("started_at")
                                ),
                                "activity_last_seen_at": str(
                                    live_activity_session.get("last_seen_at")
                                ),
                                "detection_count": int(
                                    live_activity_session.get("detection_count") or 1
                                ),
                                "near_miss_count": int(
                                    live_activity_session.get("near_miss_count") or 0
                                ),
                                "frames_evaluated_count": int(
                                    live_activity_session.get("frames_evaluated_count")
                                    or 0
                                ),
                                "candidate_frame_count": int(
                                    live_activity_session.get("candidate_frame_count")
                                    or 0
                                ),
                                "saved_candidate_count": int(
                                    live_activity_session.get("saved_candidate_count")
                                    or 0
                                ),
                            }
                            if live_activity_session is not None
                            else {}
                        ),
                        "frames_considered": len(cached_frames),
                        "activity_region_kind": session_region_kind,
                        "activity_region_id": session_region_id,
                        "pixel_delta_threshold": request.pixel_delta_threshold,
                        "min_changed_ratio": request.min_changed_ratio,
                        "best_changed_ratio": strongest_changed_ratio,
                        "best_changed_pixels": (
                            strongest_score.changed_pixels if strongest_score else 0
                        ),
                        "best_total_scored_pixels": (
                            strongest_score.total_pixels if strongest_score else 0
                        ),
                        "best_frame_width": (
                            best_live_frame_summary.width
                            if best_live_frame_summary is not None
                            else None
                        ),
                        "best_frame_height": (
                            best_live_frame_summary.height
                            if best_live_frame_summary is not None
                            else None
                        ),
                        "effective_threshold_used": effective_threshold_used,
                        "threshold_source": (
                            "object_verified"
                            if object_trigger is not None
                            else (
                                strongest_scoring_policy.threshold_source
                                if strongest_scoring_policy is not None
                                else "motion_fallback"
                            )
                        ),
                        "fine_motion_applied": (
                            strongest_scoring_policy.fine_motion_applied
                            if strongest_scoring_policy is not None
                            else False
                        ),
                        "bird_sized_feeder_motion": request.bird_sized_feeder_motion,
                        "min_triggered_frames": request.min_triggered_frames,
                        "max_gap_frames": request.max_gap_frames,
                        "frame_sequence_start": cached_frames[0].sequence,
                        "image_quality_warnings": image_quality_warnings,
                        "detector_evidence": (
                            json.dumps(
                                live_activity_session.get("detector_evidence") or {},
                                sort_keys=True,
                                default=str,
                            )
                            if live_activity_session is not None
                            else json.dumps(
                                detector_evidence_payload,
                                sort_keys=True,
                                default=str,
                            )
                        ),
                        **(
                            {
                                "activity_left": live_activity_session.get(
                                    "activity_left"
                                ),
                                "activity_top": live_activity_session.get(
                                    "activity_top"
                                ),
                                "activity_right": live_activity_session.get(
                                    "activity_right"
                                ),
                                "activity_bottom": live_activity_session.get(
                                    "activity_bottom"
                                ),
                                "activity_changed_pixel_count": live_activity_session.get(
                                    "activity_changed_pixel_count"
                                ),
                            }
                            if live_activity_session is not None
                            else _activity_bounds_scoring_fields(measured_activity)
                        ),
                    },
                    snapshot_media_asset_id=best_media_asset_id,
                    notes=request.notes
                    or "Live stream motion monitor created pending review evidence.",
                )
            )
            try:
                promoted = repository.promote_motion_evidence(
                    pending_evidence.id,
                    live_motion_promotion_payload(),
                )
            except ValueError:
                record_object_admission_promotion(
                    error_category="durable_promotion_failed"
                )
                raise
            if promoted is None:
                record_object_admission_promotion(
                    error_category="durable_promotion_unavailable"
                )
            else:
                record_object_admission_promotion(
                    event_id=promoted.event_id, visit_id=promoted.visit_id
                )
                review_motion_evidence = promoted.evidence
                review_event_id = promoted.event_id
                review_visit_id = promoted.visit_id
                created_evidence.append(promoted.evidence)
                review_activity_created = True
        except ValueError as error:
            raise _motion_evidence_error(error) from error

    if review_visit_id and review_motion_evidence:
        if review_activity_created and legacy_activity_suggestion is not None:
            try:
                review_activity_suggestion = repository.create_species_suggestion(
                    SpeciesSuggestionCreateRequest(
                        source_id=stream.source_id,
                        stream_id=stream.id,
                        event_id=review_event_id,
                        visit_id=review_visit_id,
                        media_asset_id=(
                            best_media_asset_id
                            or review_motion_evidence.snapshot_media_asset_id
                        ),
                        motion_evidence_id=review_motion_evidence.id,
                        adapter_id="live_motion_zone_suggester",
                        adapter_name="Live motion zone suggester",
                        suggested_label=legacy_activity_suggestion.label,
                        confidence=legacy_activity_suggestion.confidence,
                        rank=1,
                        alternatives=[],
                        evidence_region=None,
                        notes=legacy_activity_suggestion.reason,
                    )
                )
            except ValueError as error:
                raise _species_suggestion_error(error) from error
        elif review_activity_reused:
            review_activity_suggestion = _latest_species_suggestion_for_visit(
                repository,
                review_visit_id,
            )

    if review_motion_evidence:
        review_activity_available = False
    if review_visit_id and visit_evidence_frames:
        try:
            repository.attach_visit_evidence_media_assets(
                review_visit_id,
                visit_evidence_frames,
            )
        except ValueError as error:
            raise _motion_evidence_error(error) from error
    review_queue_item_id = (
        f"review-queue-{review_visit_id}"
        if review_visit_id
        else f"review-queue-{review_event_id}"
        if review_event_id
        else None
    )
    if (
        live_activity_session is not None
        and review_motion_evidence is not None
        and review_queue_item_id is not None
    ):
        updated_activity = (
            get_live_camera_session_manager().mark_activity_review_created(
                stream.id,
                str(live_activity_session["activity_session_id"]),
                {
                    "motion_evidence_id": review_motion_evidence.id,
                    "event_id": review_event_id,
                    "visit_id": review_visit_id,
                    "review_queue_item_id": review_queue_item_id,
                    "suggested_label": (
                        review_activity_suggestion.suggested_label
                        if review_activity_suggestion
                        else None
                    ),
                    "suggestion_id": (
                        review_activity_suggestion.id
                        if review_activity_suggestion
                        else None
                    ),
                    "suggestion_confidence": (
                        review_activity_suggestion.confidence
                        if review_activity_suggestion
                        else None
                    ),
                },
            )
        )
        if updated_activity is not None:
            live_activity_session = updated_activity.as_dict()
    status = "activity_detected" if activity_detected else "no_activity"
    live_session_status = _live_motion_session_status(
        activity_detected=activity_detected,
        duplicate_status=session_recommendation.session_status,
    )
    cooldown_remaining_seconds = _live_motion_cooldown_remaining_seconds(
        session_recommendation
    )
    existing_review_activity_reference = (
        session_recommendation.existing_activity_reference
    )
    if activity_detected and best_media_asset_id:
        message = f"{diagnostic_message or activity_summary} Best frame was saved for explicit review."
    elif activity_detected and not promoted_animal_activity:
        message = (
            "Localized motion observed; waiting for MegaDetector animal confirmation. "
            "No review item or evidence media was created."
        )
    elif activity_detected:
        message = diagnostic_message or activity_summary
    elif suppressed_zone_summaries:
        message = activity_summary
    else:
        message = diagnostic_message or "Watching live video. No activity detected yet."
    if review_activity_created:
        message = (
            f"Review activity created for {strongest_zone_name or 'live motion'}. "
            "Bird Log updates after review."
        )
    elif review_activity_reused and review_queue_item_id:
        message = "Review activity is already ready in Review Queue."
    elif live_session_status == "cooldown":
        message = (
            "Activity already captured - waiting for quiet period."
            if session_recommendation.session_status == "ongoing_activity"
            else "Cooldown active for this activity area."
        )
    response_common = {
        **common,
        "creates_event": review_event_id is not None and review_activity_created,
        "creates_visit": review_visit_id is not None and review_activity_created,
    }
    high_resolution_evidence = (
        live_activity_session.get("high_resolution_evidence")
        if isinstance(live_activity_session, dict)
        and isinstance(live_activity_session.get("high_resolution_evidence"), dict)
        else None
    )

    response = LiveMotionEvaluateResponse(
        **response_common,
        status=status,
        activity_detected=activity_detected,
        frames_considered=len(cached_frames),
        frames=frame_summaries,
        detector_preset=request.detector_preset,
        source_frame_width=(
            tracked_activity.telemetry.source_width if tracked_activity else None
        ),
        source_frame_height=(
            tracked_activity.telemetry.source_height if tracked_activity else None
        ),
        analysis_frame_width=(
            tracked_activity.telemetry.analysis_width if tracked_activity else None
        ),
        analysis_frame_height=(
            tracked_activity.telemetry.analysis_height if tracked_activity else None
        ),
        zone_source_crop_width=(
            tracked_activity.telemetry.zone_source_crop_width
            if tracked_activity
            else None
        ),
        zone_source_crop_height=(
            tracked_activity.telemetry.zone_source_crop_height
            if tracked_activity
            else None
        ),
        analysis_zone_id=(
            tracked_activity.telemetry.analysis_zone_id if tracked_activity else None
        ),
        analysis_frame_identity=(
            tracked_activity.telemetry.frame_identity if tracked_activity else None
        ),
        analysis_frame_age_ms=(
            tracked_activity.telemetry.frame_age_ms if tracked_activity else None
        ),
        duplicate_frame_count=(
            tracked_activity.telemetry.duplicate_frame_count if tracked_activity else 0
        ),
        dropped_frame_count=(
            tracked_activity.telemetry.dropped_frame_count if tracked_activity else 0
        ),
        frozen_frame_count=(
            tracked_activity.telemetry.frozen_frame_count if tracked_activity else 0
        ),
        foreground_model_state=(
            tracked_activity.foreground_model_state if tracked_activity else None
        ),
        foreground_mask_available=bool(
            tracked_activity is not None and tracked_activity.foreground_mask is not None
        ),
        foreground_mask_data_url=_tracked_foreground_mask_data_url(tracked_activity),
        global_illumination_suppressed=bool(
            tracked_activity and tracked_activity.global_illumination_suppressed
        ),
        latest_ignored_frame_reason=(
            tracked_activity.telemetry.ignored_reason if tracked_activity else None
        ),
        motion_regions=(
            [region.as_dict() for region in tracked_activity.regions]
            if tracked_activity
            else []
        ),
        tracked_objects=(
            [track.as_dict() for track in tracked_activity.tracks]
            if tracked_activity
            else []
        ),
        activity_triggers=(
            [
                {
                    "track_id": trigger.track_id,
                    "track_generation_id": trigger.track_generation_id,
                    "zone_id": trigger.zone_id,
                    "left": trigger.box[0],
                    "top": trigger.box[1],
                    "right": trigger.box[2],
                    "bottom": trigger.box[3],
                    "first_frame_identity": trigger.first_frame_identity,
                    "best_frame_identity": trigger.best_frame_identity,
                    "pretrigger_frame_identities": list(
                        trigger.pretrigger_frame_identities
                    ),
                    "reason": trigger.reason,
                    "verified": trigger.verified,
                }
                for trigger in tracked_activity.triggers
            ]
            if tracked_activity
            else []
        ),
        object_detector_available=object_detector.unavailable_reason is None,
        object_detector_unavailable_reason=object_detector.unavailable_reason,
        object_detector_zone_id=(
            str(object_detector_metadata["zone_id"])
            if object_detector_metadata["zone_id"] is not None
            else None
        ),
        object_detector_zone_source_crop_width=(
            int(object_detector_metadata["source_width"])
            if object_detector_metadata["source_width"] is not None
            else None
        ),
        object_detector_zone_source_crop_height=(
            int(object_detector_metadata["source_height"])
            if object_detector_metadata["source_height"] is not None
            else None
        ),
        object_detector_input_width=(
            int(object_detector_metadata["input_width"])
            if object_detector_metadata["input_width"] is not None
            else None
        ),
        object_detector_input_height=(
            int(object_detector_metadata["input_height"])
            if object_detector_metadata["input_height"] is not None
            else None
        ),
        object_detector_boxes=[item.as_dict() for item in object_detector.detections],
        object_detector_tracks=[item.as_dict() for item in object_detector.tracks],
        object_detector_triggers=[
            {
                "track_id": trigger.track_id,
                "track_generation_id": trigger.track_generation_id,
                "zone_id": trigger.zone_id,
                "class": trigger.label,
                "score": trigger.score,
                "left": trigger.box[0],
                "top": trigger.box[1],
                "right": trigger.box[2],
                "bottom": trigger.box[3],
                "frame_identity": trigger.frame_identity,
                "captured_at": trigger.captured_at,
                "reason": "object_verified",
            }
            for trigger in object_detector.triggers
        ],
        object_detector_cadence_seconds=object_detector.cadence_seconds,
        object_detector_inference_latency_ms=object_detector.inference_latency_ms,
        object_detector_queue_depth=object_detector.queue_depth,
        object_detector_queue_capacity=object_detector.queue_capacity,
        object_detector_dropped_frame_count=object_detector.dropped_frame_count,
        object_detector_stale_frame_count=object_detector.stale_frame_count,
        object_detector_timed_out_count=object_detector.timed_out_count,
        object_detector_runtime_state=object_detector.runtime_state,
        object_detector_model_configuration_state=object_detector.model_configuration_state,
        object_detector_model_loaded=object_detector.model_loaded,
        object_detector_worker_alive=object_detector.worker_alive,
        object_detector_in_flight_job_identity=object_detector.in_flight_job_identity,
        object_detector_in_flight_age_ms=object_detector.in_flight_age_ms,
        object_detector_last_submitted_at=object_detector.last_submitted_at,
        object_detector_last_completed_at=object_detector.last_completed_at,
        object_detector_last_completed_age_ms=object_detector.last_completed_age_ms,
        object_detector_latest_successful_inference_latency_ms=object_detector.latest_successful_inference_latency_ms,
        object_detector_worker_reset_count=object_detector.worker_reset_count,
        object_detector_recovery_count=object_detector.recovery_count,
        object_detector_queue_replacement_count=object_detector.queue_replacement_count,
        object_detector_execution_device=object_detector.execution_device,
        object_detector_last_safe_error_category=object_detector.last_safe_error_category,
        object_detector_runtime_generation=object_detector.runtime_generation,
        object_detector_admission_observability_available=(
            object_detector.admission_observability_available
        ),
        object_detector_admission_runtime_generation=(
            object_detector.admission_runtime_generation
        ),
        object_detector_admission_counters=object_detector.admission_counters,
        object_detector_current_admission_candidates=[
            dict(item) for item in object_detector.current_admission_candidates
        ],
        object_detector_recent_admission_outcomes=[
            dict(item) for item in object_detector.recent_admission_outcomes
        ],
        object_detector_last_admission_decision_at=(
            object_detector.last_admission_decision_at
        ),
        object_detector_last_successful_promotion_at=(
            object_detector.last_successful_promotion_at
        ),
        activity_trigger_source=(
            "object_verified"
            if object_trigger is not None
            else "motion_fallback"
            if best_candidate is not None
            else None
        ),
        selected_evidence_profile_id=(
            high_resolution_evidence.get("evidence_profile_id")
            if high_resolution_evidence
            else None
        ),
        high_resolution_capture_status=(
            high_resolution_evidence.get("alignment_status")
            if high_resolution_evidence
            else None
        ),
        high_resolution_frame_width=(
            high_resolution_evidence.get("full_width")
            if high_resolution_evidence
            else None
        ),
        high_resolution_frame_height=(
            high_resolution_evidence.get("full_height")
            if high_resolution_evidence
            else None
        ),
        high_resolution_crop_width=(
            high_resolution_evidence.get("crop_width")
            if high_resolution_evidence
            else None
        ),
        high_resolution_crop_height=(
            high_resolution_evidence.get("crop_height")
            if high_resolution_evidence
            else None
        ),
        high_resolution_alignment_status=(
            high_resolution_evidence.get("alignment_status")
            if high_resolution_evidence
            else None
        ),
        high_resolution_alignment_failure_code=(
            high_resolution_evidence.get("alignment_failure_code")
            if high_resolution_evidence
            else None
        ),
        high_resolution_capture_failure_code=(
            high_resolution_evidence.get("capture_failure_code")
            if high_resolution_evidence
            else None
        ),
        high_resolution_capture_latency_ms=(
            high_resolution_evidence.get("capture_latency_ms")
            if high_resolution_evidence
            else None
        ),
        high_resolution_track_to_capture_delay_ms=(
            high_resolution_evidence.get("track_to_capture_delay_ms")
            if high_resolution_evidence
            else None
        ),
        high_resolution_track_box=(
            high_resolution_evidence.get("normalized_track_box")
            if high_resolution_evidence
            else None
        ),
        high_resolution_padded_crop_box=(
            high_resolution_evidence.get("normalized_padded_crop_box")
            if high_resolution_evidence
            else None
        ),
        frame_scores=frame_score_responses,
        candidates=candidate_responses,
        activity_areas=activity_areas,
        region_source=region_source,
        uses_auto_regions=uses_auto_regions,
        strongest_zone_id=strongest_zone_id,
        strongest_zone_name=strongest_zone_name,
        strongest_zone_type=strongest_zone_type,
        strongest_activity_area=strongest_activity_area,
        strongest_activity_area_id=(
            strongest_activity_area.area_id if strongest_activity_area else None
        ),
        strongest_activity_area_label=(
            strongest_activity_area.label if strongest_activity_area else None
        ),
        suppressed_zone_summaries=suppressed_zone_summaries,
        activity_summary=activity_summary,
        strongest_changed_ratio=strongest_changed_ratio,
        requested_threshold=request.min_changed_ratio,
        effective_threshold_used=effective_threshold_used,
        threshold_used=effective_threshold_used,
        threshold_source=(
            "object_verified"
            if object_trigger is not None
            else (
                strongest_scoring_policy.threshold_source
                if strongest_scoring_policy is not None
                else "motion_fallback"
            )
            if best_candidate is not None
            else None
        ),
        fine_motion_applied=(
            strongest_scoring_policy.fine_motion_applied
            if strongest_scoring_policy is not None and object_promotion_trigger is None
            else False
        ),
        changed_pixels=strongest_score.changed_pixels if strongest_score else None,
        total_pixels=strongest_score.total_pixels if strongest_score else None,
        total_scored_pixels=strongest_score.total_pixels if strongest_score else None,
        mean_delta=strongest_score.mean_delta if strongest_score else None,
        margin_to_threshold=margin_to_threshold,
        near_miss=near_miss,
        frame_pair_sequences=(
            [diagnostic_frame_start_sequence, diagnostic_frame_end_sequence]
            if diagnostic_frame_start_sequence is not None
            and diagnostic_frame_end_sequence is not None
            else []
        ),
        feeder_threshold_applied=(
            strongest_zone_type in {ZoneType.feeder, ZoneType.birdbath, ZoneType.perch}
            if strongest_zone_type is not None
            else False
        ),
        focus_zone_id=focus_zone.id if focus_zone else None,
        focus_zone_name=focus_zone.name if focus_zone else None,
        focus_zone_type=focus_zone.zone_type if focus_zone else None,
        focus_applied=focus_zone is not None,
        evaluation_cadence_seconds=evaluation_cadence_seconds,
        image_quality_warnings=image_quality_warnings,
        strongest_zone_min_changed_ratio=strongest_zone_min_changed_ratio,
        strongest_frame_start_sequence=strongest_frame_start_sequence,
        strongest_frame_end_sequence=strongest_frame_end_sequence,
        best_frame_sequence=best_live_frame.sequence if best_live_frame else None,
        best_frame_captured_at=best_live_frame.captured_at if best_live_frame else None,
        best_media_asset_id=best_media_asset_id,
        media_asset_id=best_media_asset_id,
        **_live_activity_evaluate_fields(
            live_activity_session,
            quiet_seconds=active_quiet_seconds,
        ),
        can_create_review_activity=can_create_review_activity,
        review_activity_available=review_activity_available,
        review_activity_created=review_activity_created,
        review_activity_reused=review_activity_reused,
        review_activity_already_exists=review_activity_reused,
        existing_review_activity_reference=existing_review_activity_reference,
        session_status=live_session_status,
        cooldown_remaining_seconds=cooldown_remaining_seconds,
        last_evaluation_message=message,
        motion_evidence_id=review_motion_evidence.id
        if review_motion_evidence
        else None,
        event_id=review_event_id,
        visit_id=review_visit_id,
        review_queue_item_id=review_queue_item_id,
        review_status="needs_review" if review_queue_item_id else None,
        suggested_label=(
            review_activity_suggestion.suggested_label
            if review_activity_suggestion
            else None
        ),
        suggestion_id=(
            review_activity_suggestion.id if review_activity_suggestion else None
        ),
        suggestion_confidence=(
            review_activity_suggestion.confidence
            if review_activity_suggestion
            else None
        ),
        suggestion_reason=(
            review_activity_suggestion.notes if review_activity_suggestion else None
        ),
        suggestion_creates_truth=False,
        created_evidence=created_evidence,
        debug_cell_zones=debug_cell_zones,
        message=message,
        warnings=warnings,
    )
    _record_live_motion_session_result(response)
    return response


@app.post(
    "/api/streams/{stream_id}/live-motion/start",
    response_model=LiveMotionEvaluateResponse,
)
async def start_live_stream_motion_monitor(
    stream_id: str,
    payload: LiveMotionMonitorStartRequest | None = None,
) -> LiveMotionEvaluateResponse:
    request = payload or LiveMotionMonitorStartRequest()
    existing_policy = get_repository().get_stream_monitoring_policy(stream_id)
    if existing_policy is None:
        raise _not_found("Stream", stream_id)
    auto_create_review_candidates = (
        request.auto_create_review_candidates
        if "auto_create_review_candidates" in request.model_fields_set
        else existing_policy.auto_create_review_candidates
    )
    request = request.model_copy(
        update={"auto_create_review_candidates": auto_create_review_candidates}
    )
    get_repository().set_stream_monitoring_auto_create_review_candidates(
        stream_id,
        enabled=auto_create_review_candidates,
    )
    get_durable_monitoring_supervisor().wake()
    evaluate_request = LiveMotionEvaluateRequest(
        **request.model_dump(
            exclude={
                "interval_seconds",
                "auto_create_review_candidates",
                "auto_identify_review_candidates",
                "auto_review_quiet_seconds",
                "auto_review_min_detections",
                "create_review_activity",
            }
        ),
        create_review_activity=False,
    )
    snapshot = get_live_camera_session_manager().status(stream_id)
    if snapshot is None or snapshot.status not in {"starting", "running"}:
        return _evaluate_live_stream_motion(
            stream_id,
            evaluate_request,
            evaluation_cadence_seconds=request.interval_seconds,
        )

    def monitor_evaluate() -> dict[str, Any]:
        # Quiet-window completion belongs to the active monitor tick. Status GETs
        # remain strictly observational and cannot create review candidates.
        auto_created = _maybe_auto_create_live_review_candidate(stream_id)
        if auto_created is not None and auto_created.review_activity_created:
            snapshot_after_auto = get_live_camera_session_manager().status(stream_id)
            if (
                snapshot_after_auto is not None
                and snapshot_after_auto.last_motion_result
            ):
                return dict(snapshot_after_auto.last_motion_result)
        result = _evaluate_live_stream_motion(
            stream_id,
            evaluate_request,
            evaluation_cadence_seconds=request.interval_seconds,
        )
        _maybe_auto_create_live_review_candidate(stream_id)
        snapshot_after_auto = get_live_camera_session_manager().status(stream_id)
        if snapshot_after_auto is not None and snapshot_after_auto.last_motion_result:
            return dict(snapshot_after_auto.last_motion_result)
        return result.model_dump(mode="json")

    get_live_camera_session_manager().start_monitor(
        stream_id,
        monitor_evaluate,
        interval_seconds=request.interval_seconds,
        auto_create_review_candidates=request.auto_create_review_candidates,
        auto_identify_review_candidates=request.auto_identify_review_candidates,
        auto_review_quiet_seconds=request.auto_review_quiet_seconds,
        auto_review_min_detections=request.auto_review_min_detections,
    )
    result = _evaluate_live_stream_motion(
        stream_id,
        evaluate_request,
        evaluation_cadence_seconds=request.interval_seconds,
    )
    _maybe_auto_create_live_review_candidate(stream_id)
    return result


@app.post(
    "/api/streams/{stream_id}/live-motion/settings",
    response_model=LiveCameraSessionStatusResponse,
)
async def update_live_stream_motion_monitor_settings(
    stream_id: str,
    payload: LiveMotionMonitorSettingsRequest | None = None,
) -> LiveCameraSessionStatusResponse:
    request = payload or LiveMotionMonitorSettingsRequest()
    configuration = _stream_live_playback_config_or_404(stream_id)
    existing_policy = get_repository().get_stream_monitoring_policy(stream_id)
    if existing_policy is None:
        raise _not_found("Stream", stream_id)
    auto_create_review_candidates = (
        request.auto_create_review_candidates
        if "auto_create_review_candidates" in request.model_fields_set
        else existing_policy.auto_create_review_candidates
    )
    request = request.model_copy(
        update={"auto_create_review_candidates": auto_create_review_candidates}
    )
    get_repository().set_stream_monitoring_auto_create_review_candidates(
        stream_id,
        enabled=auto_create_review_candidates,
    )
    get_durable_monitoring_supervisor().wake()
    snapshot = get_live_camera_session_manager().update_monitor_settings(
        stream_id,
        auto_create_review_candidates=request.auto_create_review_candidates,
        auto_identify_review_candidates=request.auto_identify_review_candidates,
        auto_review_quiet_seconds=request.auto_review_quiet_seconds,
        auto_review_min_detections=request.auto_review_min_detections,
    )
    return _live_camera_session_response(
        snapshot,
        configuration,
        message=(
            "Live monitor settings updated."
            if snapshot is not None
            else "No active camera session; settings will apply when monitoring starts."
        ),
    )


@app.post(
    "/api/streams/{stream_id}/live-motion/stop",
    response_model=LiveCameraSessionStatusResponse,
)
async def stop_live_stream_motion_monitor(
    stream_id: str,
) -> LiveCameraSessionStatusResponse:
    configuration = _stream_live_playback_config_or_404(stream_id)
    snapshot = get_live_camera_session_manager().stop_monitor(stream_id)
    get_repository().disable_stream_monitoring_for_manual_stop(stream_id)
    if _durable_monitoring_supervisor is not None:
        _durable_monitoring_supervisor.wake()
    return _live_camera_session_response(
        snapshot,
        configuration,
        message="Live monitoring stopped and durable monitoring disabled.",
    )


def _record_live_motion_session_result(response: LiveMotionEvaluateResponse) -> None:
    last_activity: dict[str, Any] | None = None
    if (
        response.activity_detected
        and response.best_media_asset_id
        and not response.activity_session_id
    ):
        zone_type = (
            response.strongest_zone_type.value
            if response.strongest_zone_type is not None
            else None
        )
        last_activity = {
            "detected_at": response.evaluated_at,
            "stream_id": response.stream_id,
            "source_id": response.source_id,
            "zone_id": response.strongest_zone_id,
            "zone_name": response.strongest_zone_name,
            "zone_type": zone_type,
            "best_media_asset_id": response.best_media_asset_id,
            "best_frame_sequence": response.best_frame_sequence,
            "start_frame_sequence": response.strongest_frame_start_sequence,
            "end_frame_sequence": response.strongest_frame_end_sequence,
            "strongest_changed_ratio": response.strongest_changed_ratio,
            "threshold_used": (
                response.threshold_used
                if response.threshold_used is not None
                else response.min_changed_ratio
            ),
            "threshold_source": response.threshold_source,
            "fine_motion_applied": response.fine_motion_applied,
            "near_miss": response.near_miss,
            "margin_to_threshold": response.margin_to_threshold,
            "suppressed_zone_summaries": [
                summary.model_dump(mode="json")
                for summary in response.suppressed_zone_summaries
            ],
            "review_activity_created": response.review_activity_created,
            "motion_evidence_id": response.motion_evidence_id,
            "event_id": response.event_id,
            "visit_id": response.visit_id,
            "review_queue_item_id": response.review_queue_item_id,
            "suggested_label": response.suggested_label,
            "suggestion_id": response.suggestion_id,
            "suggestion_confidence": response.suggestion_confidence,
            "creates_truth": False,
        }
    get_live_camera_session_manager().record_motion_result(
        response.stream_id,
        response.model_dump(mode="json"),
        last_activity=last_activity,
    )


def _recorded_live_motion_response(
    response: LiveMotionEvaluateResponse,
) -> LiveMotionEvaluateResponse:
    _record_live_motion_session_result(response)
    return response


def _live_motion_review_activity_response(
    *,
    stream_id: str,
    source_id: str | None,
    status: str,
    message: str,
    activity_detected: bool = False,
    review_activity_created: bool = False,
    review_activity_reused: bool = False,
    review_activity_already_exists: bool = False,
    activity_session_id: str | None = None,
    activity_detection_count: int = 0,
    activity_started_at: datetime | None = None,
    activity_last_seen_at: datetime | None = None,
    media_asset_id: str | None = None,
    motion_evidence_id: str | None = None,
    event_id: str | None = None,
    visit_id: str | None = None,
    suggested_label: str | None = None,
    suggestion_id: str | None = None,
    suggestion_confidence: float | None = None,
    warnings: list[str] | None = None,
) -> LiveMotionReviewActivityResponse:
    review_queue_item_id = (
        f"review-queue-{visit_id}"
        if visit_id
        else f"review-queue-{event_id}"
        if event_id
        else None
    )
    return LiveMotionReviewActivityResponse(
        stream_id=stream_id,
        source_id=source_id,
        status=status,
        activity_detected=activity_detected,
        review_activity_created=review_activity_created,
        review_activity_reused=review_activity_reused,
        review_activity_already_exists=review_activity_already_exists,
        already_exists=review_activity_already_exists,
        activity_session_id=activity_session_id,
        activity_detection_count=activity_detection_count,
        activity_started_at=activity_started_at,
        activity_last_seen_at=activity_last_seen_at,
        motion_evidence_id=motion_evidence_id,
        event_id=event_id,
        visit_id=visit_id,
        media_asset_id=media_asset_id,
        review_queue_item_id=review_queue_item_id,
        suggested_label=suggested_label,
        suggestion_id=suggestion_id,
        suggestion_confidence=suggestion_confidence,
        review_status="needs_review" if review_queue_item_id else None,
        creates_event=event_id is not None and review_activity_created,
        creates_visit=visit_id is not None and review_activity_created,
        creates_truth=False,
        creates_export=False,
        message=message,
        warnings=warnings or [],
    )


def _create_live_stream_motion_review_activity(
    stream_id: str,
    *,
    auto_created: bool = False,
    activity_session_id: str | None = None,
) -> LiveMotionReviewActivityResponse:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    manager = get_live_camera_session_manager()
    snapshot = manager.status(stream_id)
    activity = None
    if activity_session_id:
        selected_activity = manager.get_activity_session(stream_id, activity_session_id)
        activity = selected_activity.as_dict() if selected_activity is not None else None
    elif snapshot is not None:
        activity = snapshot.current_activity_session or snapshot.last_activity
    if not activity:
        return _live_motion_review_activity_response(
            stream_id=stream.id,
            source_id=stream.source_id,
            status="no_activity",
            message="No stored live activity is ready for review.",
            warnings=["Start monitoring and wait for activity before creating review."],
        )

    existing_motion_evidence_id = activity.get("motion_evidence_id")
    existing_event_id = activity.get("event_id")
    existing_visit_id = activity.get("visit_id")
    if existing_motion_evidence_id:
        return _live_motion_review_activity_response(
            stream_id=stream.id,
            source_id=stream.source_id,
            status="already_exists",
            message="Review activity is already ready in Review Queue.",
            activity_detected=True,
            review_activity_reused=True,
            review_activity_already_exists=True,
            activity_session_id=activity.get("activity_session_id"),
            activity_detection_count=activity.get("detection_count") or 0,
            activity_started_at=_live_activity_datetime(activity.get("started_at")),
            activity_last_seen_at=_live_activity_datetime(activity.get("last_seen_at")),
            media_asset_id=activity.get("best_media_asset_id"),
            motion_evidence_id=existing_motion_evidence_id,
            event_id=existing_event_id,
            visit_id=existing_visit_id,
            suggested_label=activity.get("suggested_label"),
            suggestion_id=activity.get("suggestion_id"),
            suggestion_confidence=activity.get("suggestion_confidence"),
        )

    if activity.get("promotion_category") != "animal":
        return _live_motion_review_activity_response(
            stream_id=stream.id,
            source_id=stream.source_id,
            status="waiting_for_detector_promotion",
            message=(
                "Stored motion remains transient until MegaDetector confirms an animal."
            ),
            activity_detected=bool(activity.get("detection_count")),
            activity_session_id=activity.get("activity_session_id"),
            activity_detection_count=activity.get("detection_count") or 0,
            activity_started_at=_live_activity_datetime(activity.get("started_at")),
            activity_last_seen_at=_live_activity_datetime(activity.get("last_seen_at")),
            warnings=[
                "Unconfirmed motion cannot create media, an Event, a Visit, or a Review Queue item."
            ],
        )

    if int(activity.get("detection_count") or 0) <= 0:
        return _live_motion_review_activity_response(
            stream_id=stream.id,
            source_id=stream.source_id,
            status="unavailable",
            message="Stored live activity needs confirmed activity before review.",
            activity_detected=False,
            activity_session_id=activity.get("activity_session_id"),
            activity_detection_count=0,
            activity_started_at=_live_activity_datetime(activity.get("started_at")),
            activity_last_seen_at=_live_activity_datetime(activity.get("last_seen_at")),
            media_asset_id=activity.get("best_media_asset_id"),
            warnings=[
                "Near-miss-only activity remains status evidence, not review activity."
            ],
        )

    policy_snapshot = activity.get("monitoring_policy")
    started_at = _live_activity_datetime(activity.get("started_at"))
    last_seen_at = _live_activity_datetime(activity.get("last_seen_at"))
    if auto_created and activity.get("finalized_reason") == "brief_activity":
        return _live_motion_review_activity_response(
            stream_id=stream.id,
            source_id=stream.source_id,
            status="waiting_for_sustained_activity",
            message="This Zone is waiting for sustained activity before opening a Visit.",
            activity_detected=True,
            activity_session_id=activity.get("activity_session_id"),
            activity_detection_count=activity.get("detection_count") or 0,
            activity_started_at=started_at,
            activity_last_seen_at=last_seen_at,
            warnings=["Very brief activity remains monitoring evidence, not a Visit."],
        )

    zone_id = activity.get("zone_id")
    best_media_asset_id = activity.get("best_media_asset_id")
    visit_evidence_frames: list[dict[str, Any]] = []
    if not best_media_asset_id and activity.get("activity_session_id"):
        best_media_asset_id, activity = _ensure_live_activity_best_media_asset(
            repository=repository,
            stream=stream,
            activity=activity,
        )
    if not best_media_asset_id:
        return _live_motion_review_activity_response(
            stream_id=stream.id,
            source_id=stream.source_id,
            status="unavailable",
            message="Stored live activity is missing best-frame evidence.",
            activity_detected=True,
            activity_session_id=activity.get("activity_session_id"),
            activity_detection_count=activity.get("detection_count") or 0,
            activity_started_at=_live_activity_datetime(activity.get("started_at")),
            activity_last_seen_at=_live_activity_datetime(activity.get("last_seen_at")),
            media_asset_id=best_media_asset_id,
            warnings=["Create review activity requires saved best-frame evidence."],
        )

    high_resolution_frames, preferred_media_asset_id, activity = (
        _ensure_live_activity_high_resolution_media_assets(
            repository=repository,
            stream=stream,
            activity=activity,
            monitoring_media_asset_id=str(best_media_asset_id),
        )
    )
    evidence_frame_limit = max(
        1,
        live_camera_session.DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES
        - len(high_resolution_frames),
    )
    evidence_frames, activity = _ensure_live_activity_evidence_media_assets(
        repository=repository,
        stream=stream,
        activity=activity,
        best_media_asset_id=str(best_media_asset_id),
        maximum_frames=evidence_frame_limit,
    )
    # Keep the established monitoring primary on a high-resolution failure.
    # When a high-resolution still exists, it owns the primary slot instead.
    if high_resolution_frames:
        for frame in evidence_frames:
            frame["is_primary"] = False
    visit_evidence_frames = high_resolution_frames + evidence_frames
    best_media_asset_id = preferred_media_asset_id

    zone_name = activity.get("zone_name")
    promotion_attempted = False
    try:
        pending_evidence = repository.create_motion_evidence(
            MotionEvidenceCreateRequest(
                source_id=stream.source_id,
                stream_id=stream.id,
                zone_id=zone_id,
                start_frame_index=activity.get("start_frame_sequence"),
                end_frame_index=activity.get("end_frame_sequence"),
                best_frame_index=activity.get("best_frame_sequence"),
                best_frame_time=(
                    activity.get("best_frame_captured_at").isoformat()
                    if isinstance(activity.get("best_frame_captured_at"), datetime)
                    else str(activity.get("best_frame_captured_at"))
                    if activity.get("best_frame_captured_at")
                    else str(activity.get("detected_at"))
                    if activity.get("detected_at")
                    else None
                ),
                peak_changed_ratio=activity.get("best_changed_ratio")
                or activity.get("strongest_changed_ratio", 0.0),
                triggered_frame_count=activity.get("detection_count") or 1,
                scoring_config={
                    "source": "live_stream_motion_session_activity",
                    "activity_session_id": activity.get("activity_session_id"),
                    "activity_region_kind": activity.get("region_kind"),
                    "activity_region_id": activity.get("region_id"),
                    # MotionEvidence metadata permits only shallow values; retain the
                    # full per-Zone policy as immutable evidence provenance.
                    "monitoring_policy": (
                        json.dumps(policy_snapshot, sort_keys=True)
                        if isinstance(policy_snapshot, dict)
                        else None
                    ),
                    "detection_count": activity.get("detection_count") or 1,
                    "near_miss_count": activity.get("near_miss_count") or 0,
                    "frames_evaluated_count": activity.get("frames_evaluated_count")
                    or 0,
                    "candidate_frame_count": activity.get("candidate_frame_count") or 0,
                    "saved_candidate_count": activity.get("saved_candidate_count") or 0,
                    "visit_evidence_frame_limit": len(visit_evidence_frames),
                    "visit_evidence_frames": visit_evidence_frames,
                    "high_resolution_evidence": json.dumps(
                        activity.get("high_resolution_evidence") or {},
                        sort_keys=True,
                        default=str,
                    ),
                    "activity_started_at": str(activity.get("started_at"))
                    if activity.get("started_at")
                    else "",
                    "activity_last_seen_at": str(activity.get("last_seen_at"))
                    if activity.get("last_seen_at")
                    else "",
                    "best_changed_ratio": activity.get("best_changed_ratio")
                    or activity.get("strongest_changed_ratio", 0.0),
                    "best_changed_pixels": activity.get("best_changed_pixels") or 0,
                    "best_total_scored_pixels": (
                        activity.get("best_total_scored_pixels") or 0
                    ),
                    "best_frame_width": activity.get("best_frame_width"),
                    "best_frame_height": activity.get("best_frame_height"),
                    "threshold_used": activity.get("effective_threshold_used")
                    or activity.get("threshold_used"),
                    "effective_threshold_used": activity.get("effective_threshold_used")
                    or activity.get("threshold_used")
                    or 0.0,
                    "threshold_source": activity.get("threshold_source"),
                    "fine_motion_applied": activity.get("fine_motion_applied"),
                    "image_quality_warnings": list(
                        activity.get("image_quality_warnings") or []
                    ),
                    "activity_left": activity.get("activity_left"),
                    "activity_top": activity.get("activity_top"),
                    "activity_right": activity.get("activity_right"),
                    "activity_bottom": activity.get("activity_bottom"),
                    "activity_changed_pixel_count": activity.get(
                        "activity_changed_pixel_count"
                    ),
                    "detector_evidence": json.dumps(
                        activity.get("detector_evidence") or {},
                        sort_keys=True,
                        default=str,
                    ),
                    "creates_truth": False,
                },
                snapshot_media_asset_id=best_media_asset_id,
                notes=(
                    "Auto-created pending review evidence from completed live activity session."
                    if auto_created
                    else "Live stream motion monitor created pending review evidence."
                ),
            )
        )
        promotion_attempted = True
        promoted = repository.promote_motion_evidence(
            pending_evidence.id,
            MotionEvidencePromoteRequest(
                event_title=(
                    f"Live motion activity in {zone_name}"
                    if zone_name
                    else "Live motion activity"
                ),
                visit_label_hint=(
                    "unknown_bird"
                    if activity.get("zone_type")
                    in {
                        ZoneType.feeder.value,
                        ZoneType.birdbath.value,
                        ZoneType.perch.value,
                    }
                    else "unknown_animal"
                ),
                notes=(
                    "Auto-created review activity from completed live stream motion."
                    if auto_created
                    else "User created review activity from stored live stream motion."
                ),
                create_event=True,
                create_visit=True,
                attach_snapshot_media_asset_id=best_media_asset_id,
            ),
        )
    except ValueError as error:
        if promotion_attempted:
            get_live_object_detector_manager().record_admission_promotion(
                stream_id=stream_id,
                track_generation_id=activity.get("track_generation_id"),
                error_category="durable_promotion_failed",
            )
        raise _motion_evidence_error(error) from error

    if promoted is None:
        if promotion_attempted:
            get_live_object_detector_manager().record_admission_promotion(
                stream_id=stream_id,
                track_generation_id=activity.get("track_generation_id"),
                error_category="durable_promotion_unavailable",
            )
        raise HTTPException(
            status_code=409, detail="Live review activity could not be created."
        )

    if promotion_attempted:
        get_live_object_detector_manager().record_admission_promotion(
            stream_id=stream_id,
            track_generation_id=activity.get("track_generation_id"),
            event_id=promoted.event_id,
            visit_id=promoted.visit_id,
            error_category=(
                "durable_promotion_missing_visit"
                if promoted.visit_id is None
                else None
            ),
        )

    if promoted.visit_id and visit_evidence_frames:
        try:
            repository.attach_visit_evidence_media_assets(
                promoted.visit_id,
                visit_evidence_frames,
            )
        except ValueError as error:
            raise _motion_evidence_error(error) from error

    updates = {
        "review_activity_created": True,
        "motion_evidence_id": promoted.evidence.id,
        "event_id": promoted.event_id,
        "visit_id": promoted.visit_id,
        "review_queue_item_id": (
            f"review-queue-{promoted.visit_id}"
            if promoted.visit_id
            else f"review-queue-{promoted.event_id}"
            if promoted.event_id
            else None
        ),
        "suggested_label": None,
        "suggestion_id": None,
        "suggestion_confidence": None,
        "creates_truth": False,
    }
    activity_session_id = activity.get("activity_session_id")
    if activity_session_id:
        manager.mark_activity_review_created(
            stream_id,
            str(activity_session_id),
            updates,
        )
        snapshot = manager.status(stream_id)
    else:
        snapshot = manager.update_last_activity(stream_id, updates)
    if snapshot is not None and snapshot.last_motion_result is not None:
        updated_result = dict(snapshot.last_motion_result)
        updated_result.update(
            {
                "review_activity_created": True,
                "review_activity_available": False,
                "review_activity_reused": False,
                "review_activity_already_exists": False,
                "motion_evidence_id": promoted.evidence.id,
                "event_id": promoted.event_id,
                "visit_id": promoted.visit_id,
                "review_queue_item_id": updates["review_queue_item_id"],
                "review_status": "needs_review",
                "best_media_asset_id": best_media_asset_id,
                "media_asset_id": best_media_asset_id,
                "activity_session_id": activity.get("activity_session_id"),
                "activity_detection_count": activity.get("detection_count") or 1,
                "activity_near_miss_count": activity.get("near_miss_count") or 0,
                "activity_frames_evaluated_count": (
                    activity.get("frames_evaluated_count") or 0
                ),
                "activity_candidate_frame_count": (
                    activity.get("candidate_frame_count") or 0
                ),
                "activity_saved_candidate_count": (
                    activity.get("saved_candidate_count") or 0
                ),
                "activity_session_duration_seconds": (
                    activity.get("session_duration_seconds") or 0.0
                ),
                "activity_started_at": activity.get("started_at"),
                "activity_last_seen_at": activity.get("last_seen_at"),
                "activity_completed_at": activity.get("completed_at"),
                "activity_ready_for_review": True,
                "activity_manual_review_needed": False,
                "activity_review_state": "review_candidate_created",
                "activity_quiet_remaining_seconds": None,
                "notification_event": "review_candidate_ready",
                "suggested_label": updates["suggested_label"],
                "suggestion_id": updates["suggestion_id"],
                "suggestion_confidence": updates["suggestion_confidence"],
                "message": (
                    "Review activity auto-created. Bird Log updates after review."
                    if auto_created
                    else "Review activity created. Bird Log updates after review."
                ),
                "last_evaluation_message": (
                    "Review activity auto-created. Bird Log updates after review."
                    if auto_created
                    else "Review activity created. Bird Log updates after review."
                ),
                "creates_event": True,
                "creates_visit": True,
                "creates_truth": False,
                "creates_export": False,
            }
        )
        manager.record_motion_result(
            stream_id,
            updated_result,
            last_activity={**(snapshot.last_activity or {}), **updates},
        )
    return _live_motion_review_activity_response(
        stream_id=stream.id,
        source_id=stream.source_id,
        status="created",
        message=(
            "Review activity auto-created. Bird Log updates after review."
            if auto_created
            else "Review activity created. Bird Log updates after review."
        ),
        activity_detected=True,
        review_activity_created=True,
        activity_session_id=activity.get("activity_session_id"),
        activity_detection_count=activity.get("detection_count") or 1,
        activity_started_at=_live_activity_datetime(activity.get("started_at")),
        activity_last_seen_at=_live_activity_datetime(activity.get("last_seen_at")),
        media_asset_id=best_media_asset_id,
        motion_evidence_id=promoted.evidence.id,
        event_id=promoted.event_id,
        visit_id=promoted.visit_id,
        suggested_label=None,
        suggestion_id=None,
        suggestion_confidence=None,
    )


@app.post(
    "/api/streams/{stream_id}/live-motion/review-activity",
    response_model=LiveMotionReviewActivityResponse,
)
async def create_live_stream_motion_review_activity(
    stream_id: str,
) -> LiveMotionReviewActivityResponse:
    result = _create_live_stream_motion_review_activity(stream_id)
    _maybe_schedule_automatic_review_identification(stream_id, result)
    return result


def _refresh_live_activity_review_state(
    stream_id: str,
    *,
    activity_session_id: str | None = None,
) -> dict[str, Any] | None:
    manager = get_live_camera_session_manager()
    snapshot = manager.status(stream_id)
    if snapshot is None:
        return None
    if activity_session_id:
        selected_activity = manager.get_activity_session(stream_id, activity_session_id)
        activity = selected_activity.as_dict() if selected_activity is not None else None
    else:
        activity = snapshot.current_activity_session or snapshot.last_activity
    if not activity:
        return None
    selected_session_id = activity.get("activity_session_id")
    if not selected_session_id:
        return activity
    quiet_seconds = snapshot.auto_review_quiet_seconds
    if _live_activity_ready_for_review(activity, quiet_seconds=quiet_seconds):
        updated = manager.mark_activity_ready_for_review(
            stream_id,
            str(selected_session_id),
            quiet_seconds=quiet_seconds,
        )
        return updated.as_dict() if updated is not None else activity
    return activity

def _maybe_auto_create_live_review_candidate(
    stream_id: str,
) -> LiveMotionReviewActivityResponse | None:
    manager = get_live_camera_session_manager()
    snapshot = manager.status(stream_id)
    if snapshot is None or not snapshot.monitor_running:
        return None

    # Local quiet cleanup is independent of product auto-create. A reset or a
    # user-disabled candidate setting must never strand transient sessions.
    ready_sessions = manager.mark_quiet_activity_sessions_ready_for_review(
        stream_id,
        quiet_seconds=snapshot.auto_review_quiet_seconds,
    )
    if not snapshot.auto_create_review_candidates:
        return None
    latest_result: LiveMotionReviewActivityResponse | None = None
    for activity in ready_sessions:
        if activity.review_activity_created or activity.promotion_category != "animal":
            continue
        if activity.detection_count < snapshot.auto_review_min_detections:
            continue
        claimed = manager.claim_activity_finalization(
            stream_id, activity.activity_session_id
        )
        if claimed is None:
            continue
        try:
            result = _create_live_stream_motion_review_activity(
                stream_id,
                auto_created=True,
                activity_session_id=activity.activity_session_id,
            )
        except HTTPException as error:
            manager.release_activity_finalization(stream_id, activity.activity_session_id)
            manager.record_auto_review_error(stream_id, str(error.detail))
            continue

        if result.review_activity_created and result.motion_evidence_id:
            manager.record_auto_review_created(
                stream_id,
                {
                    "created_at": datetime.now(UTC),
                    "motion_evidence_id": result.motion_evidence_id,
                    "event_id": result.event_id,
                    "visit_id": result.visit_id,
                    "review_queue_item_id": result.review_queue_item_id,
                },
            )
            _maybe_schedule_automatic_review_identification(stream_id, result)
            latest_result = result
        elif result.status == "already_exists":
            manager.mark_activity_review_created(
                stream_id,
                activity.activity_session_id,
                {
                    "motion_evidence_id": result.motion_evidence_id,
                    "event_id": result.event_id,
                    "visit_id": result.visit_id,
                    "review_queue_item_id": result.review_queue_item_id,
                    "creates_truth": False,
                },
            )
            latest_result = result
        elif result.status != "created":
            manager.release_activity_finalization(stream_id, activity.activity_session_id)
            manager.record_auto_review_error(stream_id, result.message)
        else:
            manager.release_activity_finalization(stream_id, activity.activity_session_id)
            latest_result = result
    return latest_result

def _maybe_schedule_automatic_review_identification(
    stream_id: str,
    result: LiveMotionReviewActivityResponse,
) -> bool:
    manager = get_live_camera_session_manager()
    snapshot = manager.status(stream_id)
    if (
        snapshot is None
        or not snapshot.monitor_running
        or not snapshot.auto_identify_review_candidates
        or not result.review_activity_created
        or not result.visit_id
        or not result.media_asset_id
    ):
        return False
    return get_automatic_review_identification_assist().schedule(
        get_repository(),
        visit_id=result.visit_id,
        on_update=lambda update: manager.record_auto_identification_update(
            stream_id, update.as_dict()
        ),
    )


def _live_frame_timestamp(
    frames: list[live_frame_cache.LiveFrame],
    frame_sequence: int | None,
) -> str | None:
    if frame_sequence is None:
        return None
    frame = next(
        (candidate for candidate in frames if candidate.sequence == frame_sequence),
        None,
    )
    return frame.captured_at.isoformat() if frame else None


@app.post(
    "/api/motion/evidence", response_model=MotionEvidenceResponse, status_code=201
)
async def create_motion_evidence(
    payload: MotionEvidenceCreateRequest,
) -> MotionEvidenceResponse:
    # Motion Evidence is local product evidence, not review/export truth.
    # Creation does not promote events, visits, labels, or species IDs.
    try:
        return get_repository().create_motion_evidence(payload)
    except ValueError as error:
        raise _motion_evidence_error(error) from error


@app.get("/api/motion/evidence", response_model=MotionEvidenceListResponse)
async def list_motion_evidence(
    status: MotionEvidenceStatus | None = None,
    zone_id: str | None = None,
) -> MotionEvidenceListResponse:
    return MotionEvidenceListResponse(
        motion_evidence=get_repository().list_motion_evidence(
            status=status,
            zone_id=zone_id,
        )
    )


@app.post(
    "/api/motion-evidence/bulk-action",
    response_model=MotionEvidenceBulkActionResponse,
)
async def bulk_motion_evidence_action(
    payload: MotionEvidenceBulkActionRequest,
) -> MotionEvidenceBulkActionResponse:
    return get_repository().bulk_motion_evidence_action(payload)


@app.get("/api/motion/evidence/{evidence_id}", response_model=MotionEvidenceResponse)
async def get_motion_evidence(evidence_id: str) -> MotionEvidenceResponse:
    evidence = get_repository().get_motion_evidence(evidence_id)
    if evidence is None:
        raise _not_found("Motion Evidence", evidence_id)
    return evidence


@app.post(
    "/api/motion/evidence/{evidence_id}/attach-media",
    response_model=MotionEvidenceResponse,
)
async def attach_motion_evidence_media(
    evidence_id: str,
    payload: MotionEvidenceAttachMediaRequest,
) -> MotionEvidenceResponse:
    try:
        evidence = get_repository().attach_motion_evidence_media(
            evidence_id,
            payload.snapshot_media_asset_id,
        )
    except ValueError as error:
        raise _motion_evidence_error(error) from error
    if evidence is None:
        raise _not_found("Motion Evidence", evidence_id)
    return evidence


@app.post(
    "/api/motion/evidence/{evidence_id}/promote",
    response_model=MotionEvidencePromoteResponse,
)
async def promote_motion_evidence(
    evidence_id: str,
    payload: MotionEvidencePromoteRequest | None = None,
) -> MotionEvidencePromoteResponse:
    try:
        promoted = get_repository().promote_motion_evidence(
            evidence_id,
            payload or MotionEvidencePromoteRequest(),
        )
    except ValueError as error:
        raise _motion_evidence_error(error) from error
    if promoted is None:
        raise _not_found("Motion Evidence", evidence_id)
    return promoted


@app.post(
    "/api/motion/evidence/{evidence_id}/ignore", response_model=MotionEvidenceResponse
)
async def ignore_motion_evidence(evidence_id: str) -> MotionEvidenceResponse:
    try:
        evidence = get_repository().ignore_motion_evidence(evidence_id)
    except ValueError as error:
        raise _motion_evidence_error(error) from error
    if evidence is None:
        raise _not_found("Motion Evidence", evidence_id)
    return evidence


@app.post(
    "/api/species-suggestions",
    response_model=SpeciesSuggestionResponse,
    status_code=201,
)
async def create_species_suggestion(
    payload: SpeciesSuggestionCreateRequest,
) -> SpeciesSuggestionResponse:
    # Species suggestions are classifier evidence only. Review labels remain truth.
    try:
        return get_repository().create_species_suggestion(payload)
    except ValueError as error:
        raise _species_suggestion_error(error) from error


@app.post(
    "/api/species-suggestions/mock",
    response_model=SpeciesSuggestionResponse,
    status_code=201,
)
async def create_mock_species_suggestion(
    payload: MockSpeciesSuggestionRequest,
) -> SpeciesSuggestionResponse:
    repository = get_repository()
    visit = repository.get_visit(payload.visit_id)
    if visit is None:
        raise _not_found("Visit", payload.visit_id)

    event = repository.get_event(visit.event_id)
    if event is None:
        raise _not_found("Event", visit.event_id)

    stream = repository.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    media_asset = repository.media_asset_for_path(visit.representative_media_path)
    notes = (
        payload.notes.strip()
        if payload.notes and payload.notes.strip()
        else (
            "Mock/demo SpeciesSuggestion evidence for Visit review. "
            "No model runtime or media inspection was run."
        )
    )
    suggestion_payload = SpeciesSuggestionCreateRequest(
        source_id=stream.source_id,
        stream_id=stream.id,
        event_id=event.id,
        visit_id=visit.id,
        media_asset_id=media_asset.id if media_asset else None,
        adapter_id=payload.adapter_id.strip(),
        adapter_name=payload.adapter_name.strip(),
        suggested_label=(
            payload.suggested_label.strip()
            if payload.suggested_label is not None
            else "unknown_bird"
        ),
        confidence=payload.confidence,
        rank=1,
        alternatives=[],
        evidence_region=None,
        notes=notes,
    )
    try:
        return repository.create_species_suggestion(suggestion_payload)
    except ValueError as error:
        raise _species_suggestion_error(error) from error


@app.get("/api/species-suggestions", response_model=SpeciesSuggestionListResponse)
async def list_species_suggestions(
    status: SpeciesSuggestionStatus | None = None,
    visit_id: str | None = None,
    event_id: str | None = None,
    media_asset_id: str | None = None,
    suggested_label: str | None = None,
) -> SpeciesSuggestionListResponse:
    return SpeciesSuggestionListResponse(
        species_suggestions=get_repository().list_species_suggestions(
            status=status,
            visit_id=visit_id,
            event_id=event_id,
            media_asset_id=media_asset_id,
            suggested_label=suggested_label,
        )
    )


@app.get(
    "/api/species-suggestions/{suggestion_id}", response_model=SpeciesSuggestionResponse
)
async def get_species_suggestion(suggestion_id: str) -> SpeciesSuggestionResponse:
    suggestion = get_repository().get_species_suggestion(suggestion_id)
    if suggestion is None:
        raise _not_found("SpeciesSuggestion", suggestion_id)
    return suggestion


@app.post(
    "/api/species-suggestions/{suggestion_id}/status",
    response_model=SpeciesSuggestionResponse,
)
async def update_species_suggestion_status(
    suggestion_id: str,
    payload: SpeciesSuggestionStatusUpdateRequest,
) -> SpeciesSuggestionResponse:
    try:
        suggestion = get_repository().update_species_suggestion_status(
            suggestion_id,
            payload,
        )
    except ValueError as error:
        raise _species_suggestion_error(error) from error
    if suggestion is None:
        raise _not_found("SpeciesSuggestion", suggestion_id)
    return suggestion


@app.get("/api/taxonomy/labels", response_model=list[TaxonomyLabel])
async def list_taxonomy_labels() -> list[TaxonomyLabel]:
    return get_repository().list_taxonomy_labels()


@app.get("/api/species-candidate-packs", response_model=list[SpeciesCandidatePack])
async def list_species_candidate_packs(
    include_archived: bool = True,
) -> list[SpeciesCandidatePack]:
    return get_repository().list_species_candidate_packs(
        include_archived=include_archived,
    )


@app.post("/api/species-candidate-packs", response_model=SpeciesCandidatePack)
async def create_species_candidate_pack(
    payload: SpeciesCandidatePackCreate,
) -> SpeciesCandidatePack:
    try:
        return get_repository().create_species_candidate_pack(payload)
    except ValueError as error:
        raise _species_candidate_pack_error(error) from error


@app.get("/api/species-candidate-packs/{pack_id}", response_model=SpeciesCandidatePack)
async def get_species_candidate_pack(pack_id: str) -> SpeciesCandidatePack:
    pack = get_repository().get_species_candidate_pack(pack_id)
    if pack is None:
        raise _not_found("Species candidate pack", pack_id)
    return pack


@app.post(
    "/api/species-candidate-packs/{pack_id}/clone",
    response_model=SpeciesCandidatePack,
)
async def clone_species_candidate_pack(
    pack_id: str,
    payload: SpeciesCandidatePackCloneRequest,
) -> SpeciesCandidatePack:
    try:
        return get_repository().clone_species_candidate_pack(pack_id, payload)
    except ValueError as error:
        raise _species_candidate_pack_error(error) from error


@app.put("/api/species-candidate-packs/{pack_id}", response_model=SpeciesCandidatePack)
async def update_species_candidate_pack(
    pack_id: str,
    payload: SpeciesCandidatePackUpdate,
) -> SpeciesCandidatePack:
    try:
        return get_repository().update_species_candidate_pack(pack_id, payload)
    except ValueError as error:
        raise _species_candidate_pack_error(error) from error


@app.post(
    "/api/species-candidate-packs/{pack_id}/archive",
    response_model=SpeciesCandidatePack,
)
async def archive_species_candidate_pack(pack_id: str) -> SpeciesCandidatePack:
    try:
        return get_repository().archive_species_candidate_pack(pack_id)
    except ValueError as error:
        raise _species_candidate_pack_error(error) from error


@app.get("/api/taxonomy/suggestions", response_model=list[TaxonomyLabel])
async def taxonomy_suggestions(
    query: str | None = None,
    category: str | None = None,
) -> list[TaxonomyLabel]:
    return get_repository().label_suggestions(query=query, category=category)


@app.get("/api/taxonomy/labels/{label}", response_model=TaxonomyLabel)
async def get_taxonomy_label(label: str) -> TaxonomyLabel:
    taxonomy_label = get_repository().get_taxonomy_label(label)
    if taxonomy_label is None:
        raise _not_found("Taxonomy label", label)
    return taxonomy_label


@app.get("/api/sources", response_model=list[CameraSource])
async def list_sources() -> list[CameraSource]:
    return get_repository().list_sources()


@app.get("/api/camera-setup/options", response_model=CameraSetupOptionsResponse)
async def get_camera_setup_options() -> CameraSetupOptionsResponse:
    return get_repository().camera_setup_options()


def _camera_node_advertised_cameras(cameras: list[Any]) -> list[CameraNodeAdvertisedCamera]:
    """The one safe, API-shaped view of a Node's advertised cameras -- shared
    by every response that can show "what did pairing find" (a fresh pair,
    a resumed pending setup, or a refreshed draft)."""

    return [
        CameraNodeAdvertisedCamera(
            camera_id=camera.camera_id,
            display_name=camera.display_name,
            status=camera.status,
            snapshot_supported=camera.snapshot_supported,
            setup_hint=camera.setup_hint,
            provider_type=camera.provider_type,
            capture_profiles=[
                CameraNodeCaptureProfile(
                    profile_id=profile.profile_id,
                    purposes=list(profile.purposes),
                    width=profile.width,
                    height=profile.height,
                    jpeg_supported=profile.jpeg_supported,
                    max_expected_bytes=profile.max_expected_bytes,
                    capture_class=profile.capture_class,
                    geometry_group=profile.geometry_group,
                    orientation=profile.orientation,
                    mirrored=profile.mirrored,
                    same_fov=profile.same_fov,
                )
                for profile in camera.capture_profiles
            ],
        )
        for camera in cameras
    ]


def _camera_node_pending_setup_response(
    pending: CameraNodePendingSetup,
    *,
    message: str,
) -> CameraNodePendingSetupResponse:
    return CameraNodePendingSetupResponse(
        pairing_token=pending.pairing_token,
        status=pending.status,
        node_id=pending.node_id,
        display_name=pending.display_name,
        api_version=pending.api_version,
        cameras=_camera_node_advertised_cameras(pending.cameras),
        selected_camera_id=pending.selected_camera_id,
        camera_name=pending.camera_name,
        stream_name=pending.stream_name,
        zone_name=pending.zone_name,
        zone_type=pending.zone_type,
        polygon=pending.polygon,
        sensitivity=pending.sensitivity,
        monitoring_enabled=pending.monitoring_enabled,
        message=message,
    )


def _camera_node_pairing_http_error(error: CameraNodeClientError) -> HTTPException:
    """One explicit status+message per failure cause -- a malformed request,
    an expired code, a Node's genuine rejection of a wrong code, and a code
    already consumed by an earlier accepted pairing (`pairing_code_already_
    used`) are never collapsed into the same "was rejected" text. The last
    one is a local repair-state question ("did an earlier attempt already
    succeed?"), not a verdict about the code -- see
    tests/test_camera_node_repair_pairing.py for the real repro this fixes."""

    code = str(error)
    messages = {
        "node_address_invalid": "Enter a complete HTTP or HTTPS Camera Node address.",
        "node_address_requires_lan_ip": "Use an explicit local LAN IP address; discovery names are not supported yet.",
        "node_address_not_local": "Camera Node addresses must be local LAN addresses.",
        "pairing_code_malformed": "Enter the Camera Node's one-time pairing code.",
        "pairing_code_expired": "The Camera Node pairing code expired. Start the Node again for a new code.",
        "pairing_rate_limited": "Pairing attempts are temporarily limited on the Camera Node.",
        "pairing_rejected": "The Camera Node pairing code was rejected.",
        "pairing_code_already_used": (
            "This one-time code was already used for a pairing attempt. If a "
            "repair or setup already completed, refresh to resume it before "
            "requesting a new code from the Camera Node."
        ),
        "node_api_unsupported": "This Camera Node uses an unsupported API version.",
    }
    # A malformed request (never reached the Node) and a genuine Node verdict
    # are both 4xx, but distinct statuses keep them distinguishable to a
    # caller that isn't just reading the message text.
    status_by_code = {
        "node_address_invalid": 400,
        "node_address_requires_lan_ip": 400,
        "node_address_not_local": 400,
        "pairing_code_malformed": 400,
        "pairing_code_expired": 409,
        "pairing_rate_limited": 409,
        "pairing_rejected": 409,
        "pairing_code_already_used": 409,
        "node_api_unsupported": 502,
    }
    return HTTPException(
        status_code=status_by_code.get(code, 502),
        detail=messages.get(code, "Camera Node is unavailable or returned an invalid response."),
    )


@app.post("/api/camera-nodes/pair", response_model=CameraNodePairResponse)
async def pair_camera_node(payload: CameraNodePairRequest) -> CameraNodePairResponse:
    """Make the explicitly requested, bounded LAN pairing call exactly once.

    The Node's one-time code is consumed by the instant `pair()` below
    succeeds. From that point the resulting credential is durably
    persisted before this response is even built -- see "Core design
    correction" in docs/camera-node-pairing-persistence-design.md -- so a
    refresh, a closed tab, or an application restart can never strand a
    Node that already accepted its code.
    """

    try:
        # Health is deliberately an actual request so "Node found" is never metadata-only.
        get_camera_node_client().health(payload.base_address)
        pairing = get_camera_node_client().pair(payload.base_address, payload.pairing_code)
    except CameraNodeClientError as error:
        raise _camera_node_pairing_http_error(error) from None
    pending = get_repository().create_camera_node_pending_setup(
        pairing, renews_pairing_token=payload.renews_pairing_token
    )
    _track_background_task(
        asyncio.create_task(
            _refresh_camera_node_pairing_profiles(
                pairing_token=pending.pairing_token,
                pairing=pairing,
            )
        )
    )
    return CameraNodePairResponse(
        pairing_token=pending.pairing_token,
        node_id=pairing.node_id,
        display_name=pairing.display_name,
        api_version=pairing.api_version,
        cameras=_camera_node_advertised_cameras(pairing.cameras),
        message="Camera Node found and paired. Choose one advertised camera to continue setup.",
    )


@app.get("/api/camera-nodes/pending-setup", response_model=CameraNodePendingSetupResponse)
async def get_camera_node_pending_setup() -> CameraNodePendingSetupResponse:
    """Resume the most recent not-yet-completed Camera Node pairing, if any.

    A fresh page load, a reload mid-setup, or a relaunched application all
    call this the same way -- the browser never needs to remember a token
    of its own to recover an already-successful pairing. 404 (not a 200
    with an empty body) when nothing is resumable, so the wizard can tell
    "nothing paired yet" apart from a real failure.
    """

    pending = get_repository().get_latest_camera_node_pending_setup()
    if pending is None:
        raise HTTPException(status_code=404, detail="No Camera Node pairing is waiting to be resumed.")
    message = (
        "Pairing needs to be renewed."
        if pending.status == "needs_renewal"
        else "Camera Node paired. Continue setup."
    )
    return _camera_node_pending_setup_response(pending, message=message)


@app.patch("/api/camera-nodes/pending-setup/{pairing_token}", response_model=CameraNodePendingSetupResponse)
async def update_camera_node_pending_setup(
    pairing_token: str,
    payload: CameraNodePendingSetupDraftUpdate,
) -> CameraNodePendingSetupResponse:
    """Persist already-entered setup fields so they survive a refresh or
    restart exactly like the pairing itself does -- see "Required-field
    UX" in docs/camera-node-pairing-persistence-design.md."""

    pending = get_repository().update_camera_node_pending_setup_draft(pairing_token, payload)
    if pending is None:
        raise HTTPException(status_code=404, detail="This Camera Node pairing is no longer available.")
    return _camera_node_pending_setup_response(pending, message="Setup progress saved.")


@app.post("/api/camera-nodes/pending-setup/revoke", status_code=204)
async def revoke_camera_node_pending_setup(
    payload: CameraNodePendingSetupRevokeRequest,
) -> Response:
    """Explicitly, deliberately forget a Camera Node before setup finished.

    Distinct from leaving, refreshing, or discarding the wizard, which all
    preserve a resumable pending pairing -- see "Pairing semantics" in
    docs/camera-node-pairing-persistence-design.md. Uses the same
    authenticated Node revoke call as an already-completed camera; a failed
    remote request leaves the local pending setup intact so a transient
    network failure cannot silently strand it.
    """

    repository = get_repository()
    pending = repository.get_camera_node_pending_setup(payload.pairing_token)
    if pending is None:
        raise HTTPException(status_code=404, detail="This Camera Node pairing is no longer available.")
    try:
        get_camera_node_client().revoke(base_address=pending.base_address, credential=pending.credential)
    except CameraNodeClientError:
        raise HTTPException(status_code=502, detail="Camera Node could not confirm pairing revocation.") from None
    repository.delete_camera_node_pending_setup(payload.pairing_token)
    return Response(status_code=204)


@app.post("/api/camera-nodes/preview")
async def preview_camera_node(payload: CameraNodePreviewRequest) -> Response:
    """Fetch one selected Node image without creating media, evidence, or truth."""

    repository = get_repository()
    try:
        pairing = repository.resolve_camera_node_pending_pairing(
            payload.pairing_token,
            camera_id=payload.camera_id,
        )
        if pairing is None:
            raise ValueError("camera_node_pairing_expired")
        try:
            image = get_camera_node_client().snapshot(
                base_address=pairing.base_address,
                credential=pairing.credential,
                camera_id=payload.camera_id,
                recommended_timeout_seconds=pairing.recommended_snapshot_timeout_seconds,
            )
        except CameraNodeClientError as error:
            if str(error) == "authentication_rejected":
                repository.mark_camera_node_pending_setup_needs_renewal(payload.pairing_token)
            raise
    except CameraNodeClientError as error:
        messages = {
            "node_camera_not_allowed": "Choose an available camera advertised by this Camera Node.",
            "node_camera_unavailable": "The selected Camera Node camera is not currently available.",
            "authentication_rejected": "Camera Node pairing is no longer accepted. Pair the Node again.",
            "node_camera_warmup_timeout": "Camera Node warm-up timed out. Try the preview again shortly.",
            "node_snapshot_invalid": "The Camera Node did not provide a usable preview image.",
            "node_snapshot_timeout": "Camera Node preview timed out while waiting for a frame.",
            "provider_reset_required": "Camera Node needs to reset its camera provider before preview is available.",
        }
        status = 409 if str(error) in {"node_camera_not_allowed", "node_camera_unavailable", "authentication_rejected"} else 502
        raise HTTPException(
            status_code=status,
            detail=messages.get(str(error), "Camera Node is unavailable for preview."),
        ) from None
    except ValueError as error:
        if str(error) == "camera_node_pairing_expired":
            raise HTTPException(status_code=409, detail="Camera Node pairing expired. Pair the Node again.") from None
        raise
    return Response(
        content=image,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.post("/api/camera-nodes/pair/revoke", status_code=204)
async def revoke_camera_node_pairing(payload: CameraNodePairRevokeRequest) -> Response:
    repository = get_repository()
    try:
        secret = repository.camera_node_pairing_secret(payload.stream_id)
    except ValueError as error:
        if str(error) == "camera_node_provider_required":
            raise HTTPException(status_code=400, detail="This Stream is not backed by a Camera Node.") from None
        raise
    if secret is None:
        raise HTTPException(status_code=409, detail="Camera Node pairing is already unavailable.")
    address, credential = secret
    try:
        # Revocation is explicit. A failed remote request leaves the local pairing
        # intact so a transient network failure cannot silently strand the Stream.
        get_camera_node_client().revoke(base_address=address, credential=credential)
    except CameraNodeClientError:
        raise HTTPException(status_code=502, detail="Camera Node could not confirm pairing revocation.") from None
    get_durable_monitoring_supervisor().stop_stream_for_configuration(payload.stream_id)
    repository.revoke_camera_node_pairing(payload.stream_id)
    return Response(status_code=204)


@app.post("/api/camera-setup/validate", response_model=CameraSetupValidationResponse)
async def validate_camera_setup(
    payload: CameraSetupValidationRequest,
) -> CameraSetupValidationResponse:
    try:
        prepared_config = _camera_node_prepared_config(
            provider_key=payload.provider_key,
            config=payload.config,
            pairing_token=payload.node_pairing_token,
        )
        return get_repository().validate_camera_setup(
            payload.model_copy(update={"config": prepared_config})
        )
    except ValueError as error:
        messages = {
            "camera_setup_provider_unsupported": "Choose a supported camera provider.",
            "camera_setup_unsupported_fields": "This provider configuration included unsupported settings.",
            "camera_setup_invalid_url": "Enter a valid URL for the selected provider.",
            "camera_setup_invalid_node_address": "Enter a valid local LAN Camera Node address.",
            "camera_node_pairing_required": "Pair a Camera Node and select one advertised camera before validation.",
            "camera_node_pairing_expired": "Camera Node pairing expired. Pair the Node again before continuing.",
            "camera_node_camera_unavailable": "The selected Camera Node camera is no longer available. Pair or select another advertised camera.",
            "authentication_rejected": "Camera Node pairing is no longer accepted. Pair the Node again before completing setup.",
            "node_unavailable": "Camera Node is unavailable. Check the local Node before completing setup.",
        }
        raise HTTPException(status_code=400, detail=messages.get(str(error), "Camera setup could not be validated.")) from None


@app.post("/api/camera-setup/complete", response_model=CameraSetupCompletionResponse)
async def complete_camera_setup(
    payload: CameraSetupCompleteRequest,
) -> CameraSetupCompletionResponse:
    repository = get_repository()
    try:
        prepared_config = _camera_node_prepared_config(
            provider_key=payload.provider_key,
            config=payload.config,
            pairing_token=payload.node_pairing_token,
            verify_camera=True,
        )
        result = repository.complete_camera_setup(payload.model_copy(update={"config": prepared_config}))
    except ValueError as error:
        messages = {
            "source_name_exists": "A camera with that name already exists.",
            "camera_setup_validation_required": "Finish the required provider configuration before continuing.",
            "camera_setup_provider_unsupported": "Choose a supported camera provider.",
            "camera_setup_unsupported_fields": "This provider configuration included unsupported settings.",
            "camera_setup_invalid_url": "Enter a valid URL for the selected provider.",
            "camera_setup_invalid_node_address": "Enter a valid local LAN Camera Node address.",
            "camera_node_pairing_required": "Pair a Camera Node and select one advertised camera before completing setup.",
            "camera_node_pairing_expired": "Camera Node pairing expired. Pair the Node again before continuing.",
            "camera_node_camera_unavailable": "The selected Camera Node camera is no longer available. Pair or select another advertised camera.",
            "authentication_rejected": "Camera Node pairing is no longer accepted. Pair the Node again before completing setup.",
            "node_unavailable": "Camera Node is unavailable. Check the local Node before completing setup.",
            "camera_setup_idempotency_conflict": "That setup request cannot be safely repeated.",
            "camera_node_legacy_monitoring_unsupported": (
                "Camera Node streams use the Observation Engine, not legacy durable "
                "monitoring. Finish setup with monitoring off, then use Start "
                "observing afterward."
            ),
        }
        status = 409 if str(error) in {"source_name_exists", "camera_setup_idempotency_conflict"} else 400
        raise HTTPException(status_code=status, detail=messages.get(str(error), "Camera setup could not be completed.")) from None
    if payload.enable_monitoring:
        # Completion saves desired state only; the established supervisor owns any runtime start.
        get_durable_monitoring_supervisor().wake()
    return result


@app.post(
    "/api/sources",
    response_model=CameraSourceCreateResponse,
    status_code=201,
)
async def create_camera_source(
    payload: CameraSourceCreate,
) -> CameraSourceCreateResponse:
    try:
        return get_repository().create_camera_source(payload)
    except ValueError as error:
        if str(error) == "source_name_exists":
            raise HTTPException(
                status_code=409,
                detail="A camera with that name already exists.",
            ) from error
        raise


@app.patch(
    "/api/sources/{source_id}",
    response_model=CameraSourceMutationResult,
)
async def update_camera_source(
    source_id: str,
    payload: CameraSourceUpdate,
) -> CameraSourceMutationResult:
    repository = get_repository()
    try:
        result = repository.update_camera_source(source_id, payload)
    except ValueError as error:
        if str(error) == "source_name_exists":
            raise HTTPException(
                status_code=409,
                detail="A camera with that name already exists.",
            ) from error
        if str(error) == "demo_source_immutable":
            raise HTTPException(
                status_code=400,
                detail="The sample camera cannot be renamed or archived.",
            ) from error
        raise
    if result is None:
        raise _not_found("Source", source_id)

    if payload.archived is True:
        # Archiving preserves product records but explicitly cancels future restart.
        for stream in result.streams:
            repository.disable_stream_monitoring_for_manual_stop(stream.id)
            if _live_camera_session_manager is not None:
                _live_camera_session_manager.stop(stream.id, reason="source_archived")
            await get_source_monitor_manager().stop(stream.id)
        if _durable_monitoring_supervisor is not None:
            _durable_monitoring_supervisor.wake()
    return result


@app.get(
    "/api/source-provider-definitions", response_model=list[SourceProviderDefinition]
)
async def list_source_provider_definitions() -> list[SourceProviderDefinition]:
    return get_repository().list_source_provider_definitions()


# Detail and nested routes support frontend product navigation, not adapter plumbing.
@app.get("/api/sources/{source_id}", response_model=CameraSource)
async def get_source(source_id: str) -> CameraSource:
    source = get_repository().get_source(source_id)
    if source is None:
        raise _not_found("Source", source_id)
    return source


@app.get(
    "/api/sources/{source_id}/provider-configuration",
    response_model=SourceProviderConfiguration,
)
async def get_source_provider_configuration(
    source_id: str,
) -> SourceProviderConfiguration:
    configuration = get_repository().get_source_provider_configuration(source_id)
    if configuration is None:
        raise _not_found("Source", source_id)
    return configuration


@app.patch(
    "/api/sources/{source_id}/provider-configuration",
    response_model=SourceProviderConfiguration,
)
async def update_source_provider_configuration(
    source_id: str,
    payload: SourceProviderConfigurationUpdate,
) -> SourceProviderConfiguration:
    try:
        configuration = get_repository().update_source_provider_configuration(
            source_id, payload
        )
    except ValueError as error:
        if str(error) == "unknown_provider_key":
            raise HTTPException(
                status_code=400, detail="Unknown source provider key."
            ) from error
        raise
    if configuration is None:
        raise _not_found("Source", source_id)
    return configuration


@app.post(
    "/api/sources/{source_id}/webhook/validate",
    response_model=WebhookPayloadValidationResponse,
)
async def validate_source_webhook_payload(
    source_id: str,
    payload: WebhookPayloadValidationRequest,
) -> WebhookPayloadValidationResponse:
    try:
        result = get_repository().validate_webhook_payload(source_id, payload)
    except ValueError as error:
        if str(error) == "webhook_provider_required":
            raise HTTPException(
                status_code=400,
                detail="Webhook validation requires a webhook_future Source provider.",
            ) from error
        raise
    if result is None:
        raise _not_found("Source", source_id)
    return result


@app.post(
    "/api/sources/{source_id}/webhook/motion-evidence",
    response_model=WebhookMotionEvidenceResponse,
)
async def create_source_webhook_motion_evidence(
    source_id: str,
    payload: WebhookMotionEvidenceRequest,
) -> WebhookMotionEvidenceResponse:
    try:
        result = get_repository().create_webhook_motion_evidence(source_id, payload)
    except ValueError as error:
        raise _webhook_motion_evidence_error(error) from error
    if result is None:
        raise _not_found("Source", source_id)
    return result


@app.post(
    "/api/sources/{source_id}/folder-import/preview",
    response_model=SourceFolderImportPreviewResponse,
)
async def preview_source_folder_import(
    source_id: str,
    payload: SourceFolderImportPreviewRequest | None = None,
) -> SourceFolderImportPreviewResponse:
    try:
        preview = get_repository().preview_source_folder_import(
            source_id,
            payload or SourceFolderImportPreviewRequest(),
        )
    except ValueError as error:
        raise _folder_import_preview_error(error) from error
    if preview is None:
        raise _not_found("Source", source_id)
    return preview


@app.post(
    "/api/sources/{source_id}/folder-import",
    response_model=SourceFolderImportResponse,
    status_code=201,
)
async def import_source_folder_media_assets(
    source_id: str,
    payload: SourceFolderImportRequest | None = None,
) -> SourceFolderImportResponse:
    try:
        result = get_repository().import_source_folder_media_assets(
            source_id,
            payload or SourceFolderImportRequest(),
        )
    except ValueError as error:
        raise _source_folder_import_error(error) from error
    if result is None:
        raise _not_found("Source", source_id)
    return result


@app.post(
    "/api/sources/{source_id}/external-url/preview",
    response_model=ExternalUrlPreviewResponse,
)
async def fetch_external_url_preview(
    source_id: str,
    payload: ExternalUrlPreviewRequest | None = None,
) -> ExternalUrlPreviewResponse:
    repository = get_repository()
    configuration = repository.get_source_provider_configuration(source_id)
    if configuration is None:
        raise _not_found("Source", source_id)
    if configuration.provider_key != "external_url":
        raise HTTPException(
            status_code=400,
            detail="External URL preview requires an external_url Source provider.",
        )

    url = configuration.safe_config_preview.get("url")
    warnings = _external_url_preview_warnings(configuration)

    if not url or url == "not_configured":
        return ExternalUrlPreviewResponse(
            source_id=source_id,
            provider_key=configuration.provider_key,
            status="not_configured",
            message="Add an external URL before fetching a still-image preview.",
            supports_live_playback=False,
            creates_truth=False,
            creates_media_asset=False,
            warnings=warnings,
        )

    request = payload or ExternalUrlPreviewRequest()
    result = external_url_preview.fetch_external_url_preview(
        url,
        timeout_seconds=request.timeout_seconds,
        max_bytes=request.max_bytes,
    )
    return ExternalUrlPreviewResponse(
        source_id=source_id,
        provider_key=configuration.provider_key,
        status=result.status,
        message=result.message,
        fetched_at=result.fetched_at,
        content_type=result.content_type,
        content_length=result.content_length,
        bytes_read=result.bytes_read,
        preview_data_url=result.preview_data_url,
        supports_live_playback=False,
        creates_truth=False,
        creates_media_asset=False,
        warnings=[*warnings, *result.warnings],
    )


@app.post(
    "/api/sources/{source_id}/external-url/preview/save",
    response_model=ExternalUrlPreviewSaveResponse,
)
async def save_external_url_preview(
    source_id: str,
    payload: ExternalUrlPreviewSaveRequest | None = None,
) -> ExternalUrlPreviewSaveResponse:
    repository = get_repository()
    configuration = repository.get_source_provider_configuration(source_id)
    if configuration is None:
        raise _not_found("Source", source_id)
    if configuration.provider_key != "external_url":
        raise HTTPException(
            status_code=400,
            detail="External URL preview save requires an external_url Source provider.",
        )

    request = payload or ExternalUrlPreviewSaveRequest()
    warnings = _external_url_preview_warnings(configuration)
    url = configuration.safe_config_preview.get("url")
    if not url or url == "not_configured":
        return ExternalUrlPreviewSaveResponse(
            source_id=source_id,
            stream_id=request.stream_id,
            status="not_configured",
            message="Add an external URL before saving a still-image preview.",
            creates_event=False,
            creates_visit=False,
            creates_truth=False,
            warnings=warnings,
        )

    stream_id = _resolve_external_url_save_stream_id(
        repository, source_id, request.stream_id
    )
    result = external_url_preview.fetch_external_url_preview(
        url,
        timeout_seconds=request.timeout_seconds,
        max_bytes=request.max_bytes,
    )
    if (
        result.status != "available"
        or result.fetched_bytes is None
        or result.fetched_at is None
    ):
        save_status = result.status if result.status != "available" else "error"
        return ExternalUrlPreviewSaveResponse(
            source_id=source_id,
            stream_id=stream_id,
            status=save_status,
            message=result.message,
            fetched_at=result.fetched_at,
            content_type=result.content_type,
            bytes_written=0,
            creates_event=False,
            creates_visit=False,
            creates_truth=False,
            warnings=[*warnings, *result.warnings],
        )

    try:
        media_asset = repository.create_external_url_preview_media_asset(
            source_id=source_id,
            stream_id=stream_id,
            content=result.fetched_bytes,
            content_type=result.content_type or "",
            fetched_at=result.fetched_at,
            url_host=external_url_preview.safe_url_host(url),
            note=request.note,
        )
    except ValueError as error:
        raise _media_import_error(error) from error

    return ExternalUrlPreviewSaveResponse(
        source_id=source_id,
        stream_id=media_asset.stream_id,
        media_asset_id=media_asset.id,
        status="saved",
        message="Saved still-image preview as local media only. No Events, Visits, or truth were created.",
        fetched_at=media_asset.created_at,
        content_type=media_asset.content_type,
        bytes_written=media_asset.file_size_bytes,
        file_name=media_asset.filename,
        relative_path=media_asset.filename,
        creates_event=False,
        creates_visit=False,
        creates_truth=False,
        warnings=[*warnings, *result.warnings],
    )


# v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.17 Error
# taxonomy"): maps onvif_client's safe, fixed-vocabulary OnvifClientError
# codes onto this route's own small response-status enum plus an
# actionable, never-credential-bearing message. Never a generic "camera
# broken" for every failure -- see the milestone brief.
_ONVIF_DISCOVERY_ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "onvif_host_invalid": (
        "unreachable",
        "This host is not a private/local-network address MockingBird can reach.",
    ),
    "onvif_unreachable": (
        "unreachable",
        "Could not connect to this camera. Check the host and port.",
    ),
    "onvif_timeout": ("unreachable", "The camera did not respond in time."),
    "onvif_authentication_rejected": (
        "authentication_rejected",
        "The camera rejected this username/password.",
    ),
    "onvif_capabilities_unavailable": (
        "authentication_rejected",
        "The camera rejected this username/password.",
    ),
    "onvif_device_information_unavailable": (
        "error",
        "The camera responded, but device information was unavailable.",
    ),
    "onvif_no_media_service": (
        "error",
        "This camera does not advertise an ONVIF media service.",
    ),
    "onvif_no_profiles": ("no_profiles", "This camera has no media profiles to choose from."),
    "onvif_stream_uri_unavailable": (
        "error",
        "The camera did not return a usable stream URI.",
    ),
    "onvif_response_invalid": ("error", "The camera returned an unexpected response."),
}


@app.post(
    "/api/onvif/discover-profiles",
    response_model=OnvifDiscoverProfilesResponse,
)
async def discover_onvif_profiles(
    payload: OnvifDiscoverProfilesRequest,
) -> OnvifDiscoverProfilesResponse:
    """Stateless and side-effect-free (see docs/source-connection-
    provider-contract.md): connects live to the given host/credentials and
    returns device identity plus every media profile with its bare,
    credential-free stream URI. No Source needs to exist yet -- this is
    the "Add camera -> Discover with ONVIF" step; nothing here is
    persisted (see `record_onvif_profile` below for the write)."""

    client = onvif_client.OnvifClient(
        host=payload.onvif_host,
        port=payload.onvif_port,
        username=payload.onvif_username,
        password=payload.onvif_password,
    )
    try:
        # ONVIF discovery is up to four sequential blocking HTTP round
        # trips (capabilities -> device info -> profiles -> stream URI per
        # profile), bounded but longer than the single fetch `external_
        # url_preview.fetch_external_url_preview` makes synchronously
        # elsewhere in this file -- offloaded so it cannot stall the event
        # loop for other concurrent requests, matching this file's own
        # existing `asyncio.to_thread` precedent for a longer blocking call.
        result = await asyncio.to_thread(client.discover)
    except onvif_client.OnvifClientError as error:
        status_value, message = _ONVIF_DISCOVERY_ERROR_MESSAGES.get(
            str(error), ("error", "Could not reach this camera through ONVIF.")
        )
        return OnvifDiscoverProfilesResponse(status=status_value, message=message)

    return OnvifDiscoverProfilesResponse(
        status="available",
        message=f"Found {len(result.device_profiles)} media profile(s).",
        device_manufacturer=result.device_information.manufacturer,
        device_model=result.device_information.model,
        device_firmware_version=result.device_information.firmware_version,
        profiles=[
            OnvifDiscoveredProfile(
                profile_token=device_profile.profile.token,
                profile_name=device_profile.profile.name,
                advertised_width=device_profile.profile.advertised_width,
                advertised_height=device_profile.profile.advertised_height,
                encoding=device_profile.profile.encoding,
                stream_uri=device_profile.stream_uri,
            )
            for device_profile in result.device_profiles
        ],
    )


@app.post(
    "/api/sources/{source_id}/onvif/record-profile",
    response_model=OnvifRecordProfileResponse,
)
async def record_onvif_profile(
    source_id: str,
    payload: OnvifRecordProfileRequest,
) -> OnvifRecordProfileResponse:
    """Write: persists which ONVIF device/profile this Source was
    configured through, converging into the same `external_url`+rtsp
    provider configuration a manually-entered RTSP camera already uses --
    see `ProductRepository.record_onvif_profile`'s own docstring."""

    result = get_repository().record_onvif_profile(source_id, payload)
    if result is None:
        raise _not_found("Source", source_id)
    return result


async def _monitor_capture_snapshot(
    source_id: str,
    stream_id: str,
) -> MonitorSnapshotResult:
    try:
        result = await save_external_url_preview(
            source_id,
            ExternalUrlPreviewSaveRequest(
                stream_id=stream_id,
                note="Camera Monitoring Core snapshot; no truth created.",
            ),
        )
    except HTTPException as error:
        return MonitorSnapshotResult(
            media_asset_id=None,
            status="error",
            message=str(error.detail),
        )
    return MonitorSnapshotResult(
        media_asset_id=result.media_asset_id,
        status=result.status.value
        if hasattr(result.status, "value")
        else str(result.status),
        message=result.message,
    )


async def _monitor_saved_image_ids(source_id: str, stream_id: str) -> list[str]:
    return _saved_image_media_asset_ids_for_stream(
        get_repository(),
        source_id=source_id,
        stream_id=stream_id,
    )


async def _monitor_evaluate_saved_media(
    stream_id: str,
    media_asset_ids: list[str],
    create_review_activity: bool,
) -> MonitorMotionResult:
    selected_ids = media_asset_ids[-5:]
    if len(selected_ids) < 2:
        return MonitorMotionResult(
            activity_detected=False,
            session_status="needs_more_snapshots",
        )
    try:
        result = await evaluate_saved_media_motion(
            MotionEvaluateSavedMediaRequest(
                stream_id=stream_id,
                media_asset_ids=selected_ids,
                create_motion_evidence=create_review_activity,
                attach_best_snapshot=True,
                notes=(
                    "Camera Monitoring Core created pending review activity."
                    if create_review_activity
                    else None
                ),
            )
        )
    except HTTPException as error:
        return MonitorMotionResult(
            activity_detected=False,
            session_status="error",
            error=str(error.detail),
        )

    activity_area = None
    if result.strongest_activity_area_id:
        strongest_area = next(
            (
                area
                for area in result.activity_areas
                if area.area_id == result.strongest_activity_area_id
            ),
            None,
        )
        activity_area = {
            "area_id": result.strongest_activity_area_id,
            "label": result.strongest_activity_area_label,
            "best_media_asset_id": result.best_media_asset_id,
            "strongest_changed_ratio": result.strongest_changed_ratio,
            "source": strongest_area.source if strongest_area else None,
            "zone_id": strongest_area.zone_id if strongest_area else None,
            "zone_name": result.strongest_zone_name,
            "zone_type": (
                result.strongest_zone_type.value
                if result.strongest_zone_type is not None
                else None
            ),
            "left": strongest_area.left if strongest_area else None,
            "top": strongest_area.top if strongest_area else None,
            "right": strongest_area.right if strongest_area else None,
            "bottom": strongest_area.bottom if strongest_area else None,
            "activity_summary": result.activity_summary,
            "suppressed_zone_summaries": [
                summary.model_dump(mode="json")
                for summary in result.suppressed_zone_summaries
            ],
        }
    created_evidence = result.created_evidence[0] if result.created_evidence else None
    unavailable_reason = _monitor_review_unavailable_reason(result)
    best_snapshot_media_asset_id = (
        result.best_snapshot_media_asset_id or result.best_media_asset_id
    )
    return MonitorMotionResult(
        activity_detected=result.activity_detected,
        media_asset_ids=result.media_asset_ids,
        activity_area=activity_area,
        session_status=result.session_status,
        best_media_asset_id=result.best_media_asset_id,
        best_snapshot_media_asset_id=best_snapshot_media_asset_id,
        crop_plan=(
            result.crop_plan.model_dump(mode="json")
            if result.crop_plan is not None
            else None
        ),
        review_activity_available=(
            result.activity_detected
            and result.can_create_review_activity
            and result.should_create_review_activity
            and best_snapshot_media_asset_id is not None
            and created_evidence is None
            and unavailable_reason is None
        ),
        review_activity_created=created_evidence is not None,
        review_activity_unavailable_reason=unavailable_reason,
        review_activity_motion_evidence_id=(
            created_evidence.id
            if created_evidence is not None
            else result.existing_activity_reference
            if unavailable_reason == "already_exists"
            else None
        ),
    )


def _monitor_review_unavailable_reason(
    result: MotionEvaluateSavedMediaResponse,
) -> str | None:
    if not result.activity_detected:
        return "no_activity_detected"
    if not result.can_create_review_activity:
        return "review_activity_unavailable"
    if not (result.best_snapshot_media_asset_id or result.best_media_asset_id):
        return "missing_best_snapshot"
    if result.review_activity_created:
        return None
    if result.creation_skipped_reason == "activity_session_duplicate_suppressed":
        if result.session_status == "cooldown_suppressed":
            return "cooldown_suppressed"
        return "already_exists"
    if result.session_status == "cooldown_suppressed":
        return "cooldown_suppressed"
    if result.session_status == "ongoing_activity":
        return "already_exists"
    if not result.should_create_review_activity:
        return "already_exists"
    return None


def _saved_image_media_asset_ids_for_stream(
    repository: ProductRepository,
    *,
    source_id: str,
    stream_id: str,
) -> list[str]:
    return [
        asset.id
        for asset in repository.list_media_assets()
        if asset.stream_id == stream_id
        and (asset.source_id is None or asset.source_id == source_id)
        and asset.media_type == "image"
        and asset.content_type.startswith("image/")
    ]


def _monitor_stopped_state(source_id: str, stream_id: str) -> SourceMonitorState:
    return SourceMonitorState(
        monitor_id="source-monitor-not-started",
        source_id=source_id,
        stream_id=stream_id,
        status="stopped",
    )


def _monitor_status_message(state: SourceMonitorState) -> str:
    if state.review_activity_created and state.review_activity_motion_evidence_id:
        return "Review activity is ready."
    if state.review_activity_available:
        area_label = (
            (
                state.last_activity_area.get("zone_name")
                or state.last_activity_area.get("label")
            )
            if state.last_activity_area
            else None
        )
        return (
            f"Activity detected in {area_label}. Create review activity when ready."
            if area_label
            else "Activity detected. Create review activity when ready."
        )
    if state.review_activity_unavailable_reason == "cooldown_suppressed":
        return "Same recent activity. No duplicate review item is needed."
    if state.review_activity_unavailable_reason == "already_exists":
        return "Review activity already exists for this recent activity."
    if state.review_activity_unavailable_reason == "no_activity_detected":
        return "No activity detected yet."
    if state.review_activity_unavailable_reason == "missing_best_snapshot":
        return "Capture at least two snapshots before creating review activity."
    if state.status == "monitoring":
        if state.last_activity_detected is True:
            area_label = (
                (
                    state.last_activity_area.get("zone_name")
                    or state.last_activity_area.get("label")
                )
                if state.last_activity_area
                else None
            )
            return (
                f"Monitoring is active. Activity detected in {area_label}."
                if area_label
                else "Monitoring is active. Activity detected on the latest motion check."
            )
        if state.last_activity_detected is False:
            return (
                "Monitoring is active. No activity detected on the latest motion check."
            )
        return "Monitoring is active."
    if state.status == "starting":
        return "Monitoring is starting."
    if state.status == "stopped_by_user":
        return "Monitoring stopped."
    if state.status == "completed":
        if state.stop_reason == "storage_guardrail":
            return "Monitoring stopped because saved image guardrails were reached."
        if state.stop_reason == "max_runtime_reached":
            return "Monitoring stopped after the configured maximum runtime."
        if state.stop_reason == "max_snapshots_reached":
            return "Monitoring stopped after the configured snapshot limit."
        return "Monitoring completed."
    if state.status == "error":
        return state.last_error or "Monitoring stopped after an error."
    return "Monitoring is stopped."


def _monitor_crop_plan_response_from_state(
    state: SourceMonitorState,
) -> MotionCropPlanResponse | None:
    if state.crop_plan is None:
        return None
    return MotionCropPlanResponse.model_validate(state.crop_plan)


def _monitor_status_response(state: SourceMonitorState) -> SourceMonitorStatusResponse:
    return SourceMonitorStatusResponse(
        observation_provider_id=get_source_monitor_manager().provider_id,
        monitor_id=state.monitor_id,
        source_id=state.source_id,
        stream_id=state.stream_id,
        status=state.status,
        started_at=state.started_at,
        stopped_at=state.stopped_at,
        last_tick_at=state.last_tick_at,
        next_tick_at=state.next_tick_at,
        interval_seconds=state.interval_seconds,
        max_runtime_seconds=state.max_runtime_seconds,
        max_snapshots=state.max_snapshots,
        snapshots_attempted=state.snapshots_attempted,
        snapshots_saved=state.snapshots_saved,
        motion_checks_run=state.motion_checks_run,
        last_snapshot_media_asset_id=state.last_snapshot_media_asset_id,
        last_motion_media_asset_ids=state.last_motion_media_asset_ids,
        last_activity_detected=state.last_activity_detected,
        last_activity_area=state.last_activity_area,
        last_session_status=state.last_session_status,
        best_snapshot_media_asset_id=state.best_snapshot_media_asset_id,
        crop_plan=_monitor_crop_plan_response_from_state(state),
        review_activity_available=state.review_activity_available,
        review_activity_created=state.review_activity_created,
        review_activity_unavailable_reason=state.review_activity_unavailable_reason,
        review_activity_motion_evidence_id=state.review_activity_motion_evidence_id,
        review_activity_event_id=state.review_activity_event_id,
        review_activity_visit_id=state.review_activity_visit_id,
        last_error=state.last_error,
        consecutive_failures=state.consecutive_failures,
        stop_reason=state.stop_reason,
        check_motion=state.check_motion,
        create_review_activity=state.create_review_activity,
        message=_monitor_status_message(state),
    )


def _stream_source_for_monitor(
    repository: ProductRepository,
    stream_id: str,
) -> tuple[Stream, CameraSource]:
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    source = repository.get_source(stream.source_id)
    if source is None:
        raise _not_found("Source", stream.source_id)
    return stream, source


def _validate_monitor_source(
    repository: ProductRepository,
    *,
    source_id: str,
) -> None:
    configuration = repository.get_source_provider_configuration(source_id)
    if configuration is None:
        raise _not_found("Source", source_id)
    if configuration.provider_key != "external_url":
        raise HTTPException(
            status_code=400,
            detail="Start monitoring supports external URL Sources only in this phase.",
        )
    url = configuration.safe_config_preview.get("url")
    if not url or url == "not_configured":
        raise HTTPException(
            status_code=400,
            detail="Add an external URL before starting monitoring.",
        )


@app.get(
    "/api/observation-engine/status",
    response_model=ObservationEngineStatusResponse,
)
async def get_observation_engine_status(
    stream_id: str | None = None,
) -> ObservationEngineStatusResponse:
    """Report the active provider without probing cameras, workers, or models."""

    status = await get_observation_engine_registry().status(stream_id=stream_id)
    provider = status.provider
    return ObservationEngineStatusResponse(
        active_provider_id=status.active_provider_id,
        provider_id=provider.provider_id,
        provider_name=provider.display_name,
        capabilities=ObservationProviderCapabilitiesResponse(
            **provider.capabilities.__dict__,
        ),
        health=ObservationProviderHealthResponse(**provider.health.__dict__),
        creates_truth=status.creates_truth,
    )

@app.post(
    "/api/streams/{stream_id}/monitor/start",
    response_model=SourceMonitorStatusResponse,
)
async def start_stream_monitor(
    stream_id: str,
    payload: SourceMonitorStartRequest | None = None,
) -> SourceMonitorStatusResponse:
    repository = get_repository()
    stream, source = _stream_source_for_monitor(repository, stream_id)
    if source.status == SourceStatus.archived:
        raise HTTPException(
            status_code=409,
            detail="Restore this archived camera before starting monitoring.",
        )
    manager = get_source_monitor_manager()
    existing = await manager.status(stream.id)
    if existing is not None and existing.status in {"starting", "monitoring"}:
        return _monitor_status_response(existing)

    _validate_monitor_source(repository, source_id=stream.source_id)
    saved_image_count = len(
        _saved_image_media_asset_ids_for_stream(
            repository,
            source_id=stream.source_id,
            stream_id=stream.id,
        )
    )
    if saved_image_count >= 100:
        raise HTTPException(
            status_code=400,
            detail=(
                "Storage guardrails reached 100 saved images for this Stream. "
                "Review/export or clean up manually before starting monitoring."
            ),
        )

    request = payload or SourceMonitorStartRequest()
    options = SourceMonitorOptions(
        interval_seconds=request.interval_seconds,
        max_runtime_seconds=request.max_runtime_minutes * 60,
        max_snapshots=request.max_snapshots,
        check_motion=request.check_motion,
        create_review_activity=False,
    )
    state = await manager.start(
        source_id=stream.source_id,
        stream_id=stream.id,
        options=options,
    )
    return _monitor_status_response(state)


@app.post(
    "/api/streams/{stream_id}/monitor/stop",
    response_model=SourceMonitorStatusResponse,
)
async def stop_stream_monitor(stream_id: str) -> SourceMonitorStatusResponse:
    repository = get_repository()
    stream, _source = _stream_source_for_monitor(repository, stream_id)
    state = await get_source_monitor_manager().stop(stream.id)
    return _monitor_status_response(
        state or _monitor_stopped_state(stream.source_id, stream.id)
    )


@app.post(
    "/api/streams/{stream_id}/monitor/review-activity",
    response_model=SourceMonitorStatusResponse,
)
async def create_stream_monitor_review_activity(
    stream_id: str,
) -> SourceMonitorStatusResponse:
    repository = get_repository()
    stream, _source = _stream_source_for_monitor(repository, stream_id)
    manager = get_source_monitor_manager()
    state = await manager.status(stream.id)
    if state is None:
        stopped_state = _monitor_stopped_state(stream.source_id, stream.id)
        stopped_state.review_activity_unavailable_reason = "no_activity_detected"
        return _monitor_status_response(stopped_state)

    if state.review_activity_created and state.review_activity_motion_evidence_id:
        return _monitor_status_response(state)

    if not state.last_activity_detected:
        updated = await manager.mark_review_activity_result(
            stream.id,
            available=False,
            unavailable_reason="no_activity_detected",
        )
        return _monitor_status_response(updated or state)

    if not state.review_activity_available:
        unavailable_reason = state.review_activity_unavailable_reason
        if unavailable_reason is None:
            unavailable_reason = (
                "cooldown_suppressed"
                if state.last_session_status == "cooldown_suppressed"
                else "already_exists"
                if state.last_session_status == "ongoing_activity"
                else "missing_best_snapshot"
            )
        updated = await manager.mark_review_activity_result(
            stream.id,
            available=False,
            unavailable_reason=unavailable_reason,
            motion_evidence_id=(
                state.review_activity_motion_evidence_id
                if unavailable_reason == "already_exists"
                else None
            ),
        )
        return _monitor_status_response(updated or state)

    if len(state.last_motion_media_asset_ids) < 2:
        updated = await manager.mark_review_activity_result(
            stream.id,
            available=False,
            unavailable_reason="missing_best_snapshot",
        )
        return _monitor_status_response(updated or state)

    motion_result = await _monitor_evaluate_saved_media(
        stream.id,
        state.last_motion_media_asset_ids,
        True,
    )
    unavailable_reason = motion_result.review_activity_unavailable_reason
    created = (
        motion_result.review_activity_created
        and motion_result.review_activity_motion_evidence_id is not None
    )
    updated = await manager.mark_review_activity_result(
        stream.id,
        available=not created and unavailable_reason is None,
        created=created,
        unavailable_reason=unavailable_reason,
        motion_evidence_id=motion_result.review_activity_motion_evidence_id,
    )
    return _monitor_status_response(updated or state)


@app.get(
    "/api/streams/{stream_id}/monitor/status",
    response_model=SourceMonitorStatusResponse,
)
async def get_stream_monitor_status(stream_id: str) -> SourceMonitorStatusResponse:
    repository = get_repository()
    stream, _source = _stream_source_for_monitor(repository, stream_id)
    state = await get_source_monitor_manager().status(stream.id)
    return _monitor_status_response(
        state or _monitor_stopped_state(stream.source_id, stream.id)
    )


@app.get(
    "/api/sources/{source_id}/connection", response_model=SourceConnectionStatusResponse
)
async def get_source_connection_status(source_id: str) -> SourceConnectionStatus:
    status = get_repository().get_source_connection_status(source_id)
    if status is None:
        raise _not_found("Source", source_id)
    return status


@app.get(
    "/api/sources/{source_id}/setup-review", response_model=SourceSetupReviewResponse
)
async def get_source_setup_review(source_id: str) -> SourceSetupReviewResponse:
    review = get_repository().get_source_setup_review(source_id)
    if review is None:
        raise _not_found("Source", source_id)
    return review


@app.get("/api/sources/{source_id}/streams", response_model=list[Stream])
async def list_source_streams(source_id: str) -> list[Stream]:
    repository = get_repository()
    source = repository.get_source(source_id)
    if source is None:
        raise _not_found("Source", source_id)
    return repository.streams_for_source(source_id)


@app.get("/api/streams", response_model=list[Stream])
async def list_streams() -> list[Stream]:
    return get_repository().list_streams()


@app.get(
    "/api/streams/{stream_id}/species-candidate-pack",
    response_model=StreamSpeciesCandidatePackSelection,
)
async def get_stream_species_candidate_pack_selection(
    stream_id: str,
) -> StreamSpeciesCandidatePackSelection:
    selection = get_repository().get_stream_species_candidate_pack_selection(stream_id)
    if selection is None:
        raise _not_found("Stream", stream_id)
    return selection


@app.put(
    "/api/streams/{stream_id}/species-candidate-pack",
    response_model=StreamSpeciesCandidatePackSelection,
)
async def set_stream_species_candidate_pack_selection(
    stream_id: str,
    payload: StreamSpeciesCandidatePackSelectionUpdate,
) -> StreamSpeciesCandidatePackSelection:
    try:
        return get_repository().set_stream_species_candidate_pack_selection(
            stream_id,
            payload,
        )
    except ValueError as error:
        raise _species_candidate_pack_error(error) from error


@app.get(
    "/api/streams/monitoring-status",
    response_model=StreamMonitoringStatusListResponse,
)
async def list_stream_monitoring_statuses(
    limit: int = Query(default=50, ge=1, le=50),
) -> StreamMonitoringStatusListResponse:
    """A bounded status read for Dashboard; it never starts or reconciles runtime."""

    return StreamMonitoringStatusListResponse(
        items=get_repository().list_stream_monitoring_statuses(limit=limit),
        limit=limit,
        message="Showing saved monitoring intent and last-known local runtime status.",
    )


@app.get("/api/camera-health", response_model=CameraHealthListResponse)
async def list_camera_health(
    limit: int = Query(default=50, ge=1, le=50),
) -> CameraHealthListResponse:
    """Read saved health only; this endpoint never starts, probes, or retries a camera."""

    return CameraHealthListResponse(
        items=[
            _camera_health_with_pending_node_recovery(
                CameraHealthDetailResponse(health=item, message="")
            ).health
            for item in get_repository().list_stream_camera_health(limit=limit)
        ],
        limit=limit,
        message="Showing saved camera health for configured Streams.",
    )


async def _dashboard_runtime_by_stream(
    repository: ProductRepository,
) -> dict[str, DashboardStreamRuntimeStatus]:
    """Read runtime facts only; Dashboard polling must never start monitoring."""

    runtime_by_stream: dict[str, DashboardStreamRuntimeStatus] = {}
    live_manager = get_live_camera_session_manager()
    source_monitor_manager = get_source_monitor_manager()
    engine_manager = get_observation_engine_session_manager()
    for stream in repository.list_streams()[:50]:
        live_snapshot = live_manager.status(stream.id)
        source_monitor = await source_monitor_manager.status(stream.id)
        live_active = bool(live_snapshot and live_snapshot.monitor_running)
        source_active = bool(
            source_monitor and source_monitor.status in {"starting", "monitoring"}
        )
        live_session_ready = bool(
            live_snapshot and live_snapshot.status in {"starting", "running"}
        )
        source = repository.get_source(stream.source_id)
        configuration = repository.get_source_provider_configuration(stream.source_id)
        source_monitor_ready = bool(
            source is not None
            and source.status != SourceStatus.archived
            and configuration
            and configuration.provider_key == "external_url"
            and configuration.safe_config_preview.get("url") not in {None, "not_configured"}
        )
        # A paired Camera Node Stream is exclusively governed by the
        # accepted Observation Engine, never this legacy subsystem -- and
        # its own live-view session is *deliberately* paused for the whole
        # time Observation Engine owns the camera (see "Live camera
        # ownership" in architecture.md), so `live_active` above is always
        # False while a Camera Node Stream is genuinely, healthily being
        # observed. Reading the same side-effect-free engine status the
        # Stream Detail Observation panel already uses (`ObservationEngine
        # SessionManager.status`) closes that blind spot at its root rather
        # than leaving every consumer of this dict (ProductHealthPanel's
        # "Observing X of Y cameras", TodayReportPanel's monitoring-started
        # empty state, LiveCameraOverview's activity/session facts) to
        # undercount a real, working Camera Node observation session.
        engine_active = False
        # Mirrors the exact "genuinely terminal" test unified_status.py's
        # per-Stream Observation panel already uses implicitly (a non-
        # "observing" state with a real failure behind it): `state="error"`
        # (an immediate pairing/engine-load failure) or the bounded retry
        # policy's own exhausted-recovery marker,
        # `stopped_reason="camera_unavailable"` (never set for an explicit
        # user Stop, which uses "user_stopped", or a natural session end,
        # "session_ended" -- see AnalysisStreamRetryPolicy/_EngineSession in
        # engine_runtime.py). A reconnect still in its bounded retry window
        # deliberately stays `observing`/non-terminal here, matching that
        # policy's own "do not alarm on a benign reconnect" design.
        engine_terminally_unavailable = False
        engine_unavailable_message = None
        if configuration is not None and configuration.provider_key == "camera_node":
            engine_status = engine_manager.status(stream.id)
            engine_active = bool(engine_status and engine_status.observing)
            if engine_status is not None and (
                engine_status.state == "error"
                or engine_status.stopped_reason == "camera_unavailable"
            ):
                engine_terminally_unavailable = True
                engine_unavailable_message = engine_status.camera_message or engine_status.message

        if source_active:
            monitor_control = "source_monitor"
        elif engine_active:
            monitor_control = "observation_engine"
        elif live_active or live_session_ready:
            monitor_control = "live_motion"
        elif source_monitor_ready:
            monitor_control = "source_monitor"
        else:
            monitor_control = "none"

        runtime_by_stream[stream.id] = DashboardStreamRuntimeStatus(
            monitoring_active=live_active or source_active or engine_active,
            monitor_control=monitor_control,
            # Camera Node never uses this legacy start/stop toggle (the
            # Observation panel's own Start/Stop observing is the only
            # control it recognizes -- see LiveCameraOverview.tsx, which
            # already hides this toggle for `playback_kind === "camera_node"`),
            # so `can_start_monitor`/`can_stop_monitor` deliberately stay
            # scoped to the legacy subsystem alone; broadening them is out
            # of scope for this truthfulness fix.
            can_start_monitor=(
                not (live_active or source_active)
                and (live_session_ready or source_monitor_ready)
            ),
            can_stop_monitor=live_active or source_active,
            open_activity_session_count=(
                live_snapshot.open_activity_session_count if live_snapshot else 0
            ),
            ready_activity_session_count=(
                live_snapshot.ready_activity_session_count if live_snapshot else 0
            ),
            engine_terminally_unavailable=engine_terminally_unavailable,
            engine_unavailable_message=engine_unavailable_message,
        )
    return runtime_by_stream


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
async def get_dashboard_summary() -> DashboardSummary:
    repository = get_repository()
    runtime_by_stream = await _dashboard_runtime_by_stream(repository)
    return repository.dashboard_summary(runtime_by_stream)


# States a healthy or merely-idle camera can be in; anything else is a basic
# "needs attention" signal, matching DashboardPage's own `cameraHealthTone`.
_CAMERA_HEALTH_OK_STATES = {
    CameraHealthState.healthy,
    CameraHealthState.stopped,
    CameraHealthState.starting,
}


@app.get("/api/product/health", response_model=ProductHealthStatus)
async def get_product_health() -> ProductHealthStatus:
    """One bounded, basic-first "is MockingBird okay" aggregate.

    Reuses `dashboard_summary` (cameras/observation counts), `storage_summary`
    (disk writable/low-space), the existing backup library, the running app
    version, and the runtime-lifecycle marker/log path -- it computes nothing
    those surfaces do not already compute. See
    docs/local-product-packaging-design.md.
    """

    repository = get_repository()
    runtime_by_stream = await _dashboard_runtime_by_stream(repository)
    dashboard = repository.dashboard_summary(runtime_by_stream)
    storage = repository.storage_summary()

    try:
        backups = _local_backup_manager(repository).list_backups().backups
    except LocalBackupError:
        backups = []
    most_recent_backup = backups[0] if backups else None
    # Nudge only once there is something worth protecting and the user has
    # had a real chance to see backups exist -- not mid-onboarding, and
    # never once a backup has actually been created. Side-effect-free: a
    # computed fact, not a persisted/scheduled alert, so there is nothing to
    # dismiss or repeat-nag about (see ProductHealthBackupSummary).
    suggest_first_backup = repository.get_setup_state().completed and most_recent_backup is None

    needs_attention_count = sum(
        1
        for camera in dashboard.today.observation_health
        if camera.state not in _CAMERA_HEALTH_OK_STATES
    )
    storage_low_space = storage.disk_total_bytes > 0 and (
        storage.disk_free_bytes < LOW_DISK_FREE_BYTES_THRESHOLD
        or storage.disk_free_bytes / storage.disk_total_bytes < LOW_DISK_FREE_RATIO_THRESHOLD
    )

    ready = storage.is_writable and needs_attention_count == 0
    if not storage.is_writable:
        message = "MockingBird's local storage is not writable. Check that its data folder allows writes."
    elif needs_attention_count > 0:
        message = (
            f"{needs_attention_count} camera{'s' if needs_attention_count != 1 else ''} "
            "need attention."
        )
    elif storage.storage_warning:
        message = storage.storage_warning
    else:
        message = "MockingBird is ready."

    return ProductHealthStatus(
        app_version=APP_VERSION,
        ready=ready,
        message=message,
        storage_writable=storage.is_writable,
        storage_low_space=storage_low_space,
        storage_warning=storage.storage_warning,
        cameras=ProductHealthCameraSummary(needs_attention_count=needs_attention_count),
        observation=ProductHealthObservationSummary(
            configured_stream_count=dashboard.headline.real_stream_count,
            monitored_stream_count=dashboard.headline.monitored_stream_count,
        ),
        backup=ProductHealthBackupSummary(
            has_backup=most_recent_backup is not None,
            last_backup_at=most_recent_backup.created_at if most_recent_backup else None,
            last_backup_verified=(
                most_recent_backup.verification_status == "verified"
                if most_recent_backup
                else None
            ),
            suggest_first_backup=suggest_first_backup,
        ),
        previous_shutdown_clean=previous_shutdown_was_clean(),
        database_schema_version=repository.schema_status.version,
        log_path=str(current_log_path()) if current_log_path() else None,
        generated_at=datetime.now(UTC),
    )


@app.get("/api/product/instance", response_model=ProductInstanceIdentity)
async def get_product_instance_identity() -> ProductInstanceIdentity:
    """Answer "which local installation/data directory is this, and exactly
    which build," so the local launcher can tell an already-running copy of
    itself apart from an arbitrary other service (or a MockingBird instance
    forwarded from a different environment, such as WSL) that merely
    answers the same `/health` shape on the same port. `git_commit`/
    `build_id` additionally let a developer tool (see
    docs/windows-dev-deployment-design.md) prove a running instance matches
    the exact commit/build it deployed, never inferred from a folder name.
    Not otherwise part of the basic product surface -- see
    docs/camera-node-pairing-persistence-design.md.
    """

    runtime_home = current_runtime_home()
    git_commit, build_id = resolve_build_identity()
    return ProductInstanceIdentity(
        instance_id=resolve_instance_id(runtime_home) if runtime_home is not None else None,
        app_version=APP_VERSION,
        git_commit=git_commit,
        build_id=build_id,
    )


@app.get("/api/streams/{stream_id}", response_model=Stream)
async def get_stream(stream_id: str) -> Stream:
    stream = get_repository().get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return stream


def _camera_configuration_http_error(error: Exception) -> HTTPException:
    code = str(error)
    conflict_messages = {
        "camera_configuration_state_changed": "This camera changed after the edit screen opened. Refresh the configuration before saving.",
        "camera_configuration_preview_expired": "This impact preview is no longer current. Review the updated impact before saving.",
        "camera_configuration_idempotency_conflict": "That save request key was already used for a different camera change.",
        "source_name_exists": "A camera with that name already exists.",
        "camera_configuration_runtime_stop_failed": "MockingBird could not safely stop the current camera session. The saved configuration was not changed.",
    }
    validation_messages = {
        "camera_configuration_not_editable": "This camera provider cannot be edited in guided setup.",
        "camera_configuration_provider_fixed": "Camera type is fixed for an existing camera. Add a new camera for a different provider.",
        "camera_configuration_unsupported_fields": "This camera configuration included unsupported settings.",
        "camera_configuration_restricted_field": "This setting is not editable from guided camera setup.",
        "camera_configuration_secret_action_invalid": "Secret actions apply only to saved credential fields.",
        "camera_configuration_secret_action_required": "Choose Keep, Replace, or Remove before changing a saved credential.",
        "camera_configuration_secret_remove_value": "Remove a saved credential without entering a replacement value.",
        "camera_configuration_secret_replace_value": "Enter a replacement value before choosing Replace.",
        "camera_configuration_validation_required": "Finish the required camera configuration before saving.",
        "camera_configuration_no_changes": "Make a camera configuration change before saving.",
        "camera_configuration_monitoring_state_missing": "This camera is missing required local monitoring state and cannot be edited safely.",
        "camera_configuration_provider_unsupported": "This camera provider is not supported by guided editing.",
        "camera_setup_invalid_url": "Enter a valid URL for the selected camera field.",
        "camera_setup_invalid_node_address": "Enter a valid local LAN Camera Node address.",
        "camera_node_pairing_required": "Pair a Camera Node and select an advertised camera before saving.",
        "camera_node_pairing_expired": "Camera Node pairing expired. Pair the Node again before saving.",
        "camera_node_identity_changed": "This paired Node has a different identity than the one currently attached to this camera. If you intentionally replaced the Camera Node hardware, confirm the replacement to reattach it to this existing camera; otherwise add it as a separate camera instead.",
        "authentication_rejected": "Camera Node pairing is no longer accepted. Pair the Node again before saving.",
        "node_unavailable": "Camera Node is unavailable. Check the local Node before saving.",
    }
    if code in conflict_messages:
        return HTTPException(status_code=409, detail=conflict_messages[code])
    return HTTPException(
        status_code=400,
        detail=validation_messages.get(code, "Camera configuration could not be updated safely."),
    )


@app.get(
    "/api/streams/{stream_id}/camera-configuration",
    response_model=CameraConfigurationEditResponse,
)
async def get_camera_configuration_edit(
    stream_id: str,
) -> CameraConfigurationEditResponse:
    try:
        configuration = get_repository().get_camera_configuration_edit(stream_id)
    except ValueError as error:
        raise _camera_configuration_http_error(error) from None
    if configuration is None:
        raise _not_found("Stream", stream_id)
    return configuration


@app.get(
    "/api/streams/{stream_id}/camera-configuration/pending-pairing",
    response_model=CameraNodePendingSetupResponse,
)
async def get_camera_configuration_pending_pairing(
    stream_id: str,
) -> CameraNodePendingSetupResponse:
    """Resume a not-yet-saved *repair* pairing for this Stream's Camera Node.

    "Pair or repair Node" durably persists its credential the moment the
    Node accepts it -- before the repair page ever gets a chance to save it
    onto the Stream (see `create_camera_node_pending_setup`). Without this,
    a refresh, a closed tab, or simply not reaching Save yet orphans that
    already-consumed one-time code: the browser's only visible recourse is
    to re-enter it, which the Node correctly (and permanently) refuses a
    second time. 404 (not a 200 with an empty body) when nothing is
    resumable, so the repair page can tell "nothing pending" apart from a
    real failure -- exactly like first-run's `/api/camera-nodes/pending-setup`.
    """

    try:
        pending = get_repository().get_camera_node_pending_setup_for_stream(stream_id)
    except ValueError as error:
        raise _camera_configuration_http_error(error) from None
    if pending is None:
        raise HTTPException(
            status_code=404,
            detail="No Camera Node pairing is waiting to be resumed for this camera.",
        )
    message = (
        "Pairing needs to be renewed."
        if pending.status == "needs_renewal"
        else "Camera Node paired. Choose an advertised camera and save to finish repairing."
    )
    return _camera_node_pending_setup_response(pending, message=message)


@app.post(
    "/api/streams/{stream_id}/camera-configuration/preview",
    response_model=CameraConfigurationImpactPreview,
)
async def preview_camera_configuration(
    stream_id: str,
    payload: CameraConfigurationImpactPreviewRequest,
) -> CameraConfigurationImpactPreview:
    try:
        preview = get_repository().preview_camera_configuration(
            stream_id,
            _camera_node_prepared_edit_payload(payload),
        )
    except (CameraConfigurationConflictError, ValueError) as error:
        raise _camera_configuration_http_error(error) from None
    if preview is None:
        raise _not_found("Stream", stream_id)
    return preview


@app.post(
    "/api/streams/{stream_id}/camera-configuration/apply",
    response_model=CameraConfigurationApplyResponse,
)
async def apply_camera_configuration(
    stream_id: str,
    payload: CameraConfigurationApplyRequest,
) -> CameraConfigurationApplyResponse:
    try:
        result = await CameraConfigurationApplicationService(get_repository()).apply(
            stream_id,
            # An actual live check against the Node, exactly like first-run's
            # `/api/camera-setup/complete` (never its own `/validate`/preview
            # step) -- a stale or already-superseded credential is caught
            # here, before it's saved, rather than persisted as if it worked.
            _camera_node_prepared_edit_payload(payload, verify_camera=True),
        )
    except (CameraConfigurationConflictError, ValueError, RuntimeError) as error:
        raise _camera_configuration_http_error(error) from None
    if result is None:
        raise _not_found("Stream", stream_id)
    # Configuration application safely stops/replaces the live session. Keep
    # background state process-local and warm it again on the next frame.
    get_tracked_activity_detector_manager().reset(stream_id)
    if _live_object_detector_manager is not None:
        _live_object_detector_manager.reset(stream_id)
    return result


@app.get(
    "/api/streams/{stream_id}/camera-configuration/history",
    response_model=CameraConfigurationHistoryResponse,
)
async def list_camera_configuration_history(
    stream_id: str,
    limit: int = Query(default=20, ge=1, le=20),
) -> CameraConfigurationHistoryResponse:
    revisions = get_repository().list_camera_configuration_history(stream_id, limit=limit)
    if revisions is None:
        raise _not_found("Stream", stream_id)
    return CameraConfigurationHistoryResponse(
        items=revisions,
        limit=limit,
        message="Showing bounded redacted camera configuration history.",
    )


@app.get(
    "/api/streams/{stream_id}/playback", response_model=StreamPlaybackStatusResponse
)
async def get_stream_playback_status(stream_id: str) -> StreamPlaybackStatus:
    status = get_repository().get_stream_playback_status(stream_id)
    if status is None:
        raise _not_found("Stream", stream_id)
    return status


@app.get(
    "/api/streams/{stream_id}/monitoring-policy",
    response_model=StreamMonitoringPolicyResponse,
)
async def get_stream_monitoring_policy(
    stream_id: str,
) -> StreamMonitoringPolicyResponse:
    policy = get_repository().get_stream_monitoring_policy(stream_id)
    if policy is None:
        raise _not_found("Stream", stream_id)
    return policy


@app.get(
    "/api/streams/{stream_id}/runtime-status",
    response_model=StreamRuntimeStatusResponse,
)
async def get_stream_runtime_status(stream_id: str) -> StreamRuntimeStatusResponse:
    status = get_repository().get_stream_runtime_status(stream_id)
    if status is None:
        raise _not_found("Stream", stream_id)
    return status


@app.get(
    "/api/streams/{stream_id}/camera-health",
    response_model=CameraHealthDetailResponse,
)
async def get_stream_camera_health(stream_id: str) -> CameraHealthDetailResponse:
    detail = get_repository().get_stream_camera_health(stream_id)
    if detail is None:
        raise _not_found("Stream", stream_id)
    return _camera_health_with_pending_node_recovery(detail)


@app.get(
    "/api/streams/{stream_id}/camera-health/incidents",
    response_model=CameraHealthIncidentListResponse,
)
async def list_stream_camera_health_incidents(
    stream_id: str,
    limit: int = Query(default=20, ge=1, le=20),
) -> CameraHealthIncidentListResponse:
    detail = get_repository().get_stream_camera_health(stream_id, incident_limit=limit)
    if detail is None:
        raise _not_found("Stream", stream_id)
    return CameraHealthIncidentListResponse(
        items=detail.incidents,
        limit=limit,
        message="Showing bounded recent camera health history.",
    )


@app.put(
    "/api/streams/{stream_id}/monitoring-policy",
    response_model=StreamMonitoringMutationResponse,
)
async def update_stream_monitoring_policy(
    stream_id: str,
    payload: StreamMonitoringPolicyUpdate,
) -> StreamMonitoringMutationResponse:
    """Persist Enable/Disable intent first, then ask the one app supervisor to reconcile."""

    repository = get_repository()
    try:
        idempotent = repository.set_stream_monitoring_enabled(
            stream_id,
            enabled=payload.enabled,
            idempotency_key=payload.idempotency_key,
        )
    except MonitoringOperationConflictError:
        raise HTTPException(
            status_code=409,
            detail="That monitoring request key was already used for a different action.",
        ) from None
    except ValueError as error:
        if str(error) == "camera_node_legacy_monitoring_unsupported":
            raise HTTPException(
                status_code=409,
                detail=(
                    "This Stream is a paired Camera Node. Camera Node streams use "
                    "the Observation Engine (Start observing) rather than legacy "
                    "durable monitoring."
                ),
            ) from None
        raise
    if idempotent is None:
        raise _not_found("Stream", stream_id)

    get_durable_monitoring_supervisor().wake()
    policy = repository.get_stream_monitoring_policy(stream_id)
    runtime = repository.get_stream_runtime_status(stream_id)
    if policy is None or runtime is None:
        raise _not_found("Stream", stream_id)
    return StreamMonitoringMutationResponse(
        policy=policy,
        runtime=runtime,
        idempotent=idempotent,
        message=(
            "Monitoring is enabled. Local startup will wait for a healthy camera frame."
            if payload.enabled
            else "Monitoring is disabled and pending recovery has been cancelled."
        ),
    )


@app.post(
    "/api/streams/{stream_id}/runtime/retry",
    response_model=StreamMonitoringMutationResponse,
)
async def retry_stream_monitoring_runtime(
    stream_id: str,
    payload: StreamMonitoringRetryRequest,
) -> StreamMonitoringMutationResponse:
    """Retry a blocked enabled Stream explicitly; retries never start a second session."""

    repository = get_repository()
    try:
        idempotent = repository.retry_stream_monitoring(
            stream_id,
            idempotency_key=payload.idempotency_key,
        )
    except MonitoringOperationConflictError:
        raise HTTPException(
            status_code=409,
            detail="That monitoring request key was already used for a different action.",
        ) from None
    except ValueError as error:
        if str(error) == "monitoring_disabled":
            raise HTTPException(
                status_code=409,
                detail="Enable monitoring before requesting a runtime retry.",
            ) from None
        raise
    if idempotent is None:
        raise _not_found("Stream", stream_id)

    get_durable_monitoring_supervisor().wake()
    policy = repository.get_stream_monitoring_policy(stream_id)
    runtime = repository.get_stream_runtime_status(stream_id)
    if policy is None or runtime is None:
        raise _not_found("Stream", stream_id)
    return StreamMonitoringMutationResponse(
        policy=policy,
        runtime=runtime,
        idempotent=idempotent,
        message="Monitoring retry requested. The local supervisor will reuse its bounded recovery path.",
    )


def _stream_live_playback_config_or_404(
    stream_id: str,
    *,
    require_active_source: bool = False,
) -> StreamLivePlaybackConfig:
    repository = get_repository()
    configuration = repository.get_stream_live_playback_config(stream_id)
    if configuration is None:
        raise _not_found("Stream", stream_id)
    if require_active_source:
        source = repository.get_source(configuration.source_id)
        if source is None:
            raise _not_found("Source", configuration.source_id)
        if source.status == SourceStatus.archived:
            raise HTTPException(
                status_code=409,
                detail="Restore this archived camera before using Live view or capture.",
            )
    return configuration


@app.post(
    "/api/streams/{stream_id}/live-session/start",
    response_model=LiveCameraSessionStatusResponse,
)
async def start_stream_live_camera_session(
    stream_id: str,
) -> LiveCameraSessionStatusResponse:
    configuration = _stream_live_playback_config_or_404(
        stream_id,
        require_active_source=True,
    )
    _validate_live_camera_session_config(configuration)
    try:
        manager = get_live_camera_session_manager()
        existing = manager.status(stream_id)
        if existing is None or existing.status not in {"starting", "running"}:
            # Foreground state is intentionally transient. A fresh camera
            # session must warm a new model instead of comparing it with a
            # previous process' scene.
            get_tracked_activity_detector_manager().reset(stream_id)
            if _live_object_detector_manager is not None:
                _live_object_detector_manager.reset(stream_id)
        snapshot = manager.start(configuration)
    except (OSError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Camera session failed to start.",
        ) from None
    return _live_camera_session_response(snapshot, configuration)


@app.post(
    "/api/streams/{stream_id}/live-session/stop",
    response_model=LiveCameraSessionStatusResponse,
)
async def stop_stream_live_camera_session(
    stream_id: str,
) -> LiveCameraSessionStatusResponse:
    configuration = _stream_live_playback_config_or_404(stream_id)
    snapshot = get_live_camera_session_manager().stop(stream_id)
    get_tracked_activity_detector_manager().reset(stream_id)
    if _live_object_detector_manager is not None:
        _live_object_detector_manager.reset(stream_id)
    get_repository().disable_stream_monitoring_for_manual_stop(stream_id)
    if _durable_monitoring_supervisor is not None:
        _durable_monitoring_supervisor.wake()
    return _live_camera_session_response(
        snapshot,
        configuration,
        message="Camera session stopped and durable monitoring disabled.",
    )


def _observation_panel_response(
    stream_id: str, facts: unified_status.ObservationPanelFacts,
) -> ObservationSessionStatusResponse:
    """Wrap one lane's composed facts in the unified wire contract. The one
    place every lane's Start/Stop/Status handler converges, so the response
    shape is identical no matter which existing runtime produced it."""

    return ObservationSessionStatusResponse(
        stream_id=stream_id,
        state=facts.state,
        observing=facts.observing,
        message=facts.message,
        camera_connected=facts.camera_connected,
        camera_message=facts.camera_message,
        engine_available=facts.engine_available,
        engine_message=facts.engine_message,
        runtime_available=facts.runtime_available,
        started_at=facts.started_at,
        stopped_at=facts.stopped_at,
        stopped_reason=facts.stopped_reason,
        last_candidate_visit_id=facts.last_candidate_visit_id,
        last_useful_frame_at=facts.last_useful_frame_at,
        setup_action=facts.setup_action,
        retry_action=facts.retry_action,
        candidate_authority_exhausted=facts.candidate_authority_exhausted,
        candidate_authority_message=facts.candidate_authority_message,
        counts=ObservationSessionCounts(
            track_updates_observed=facts.counts.track_updates_observed,
            evidence_candidates_observed=facts.counts.evidence_candidates_observed,
            proposals_observed=facts.counts.proposals_observed,
            candidates_created=facts.counts.candidates_created,
            candidates_suppressed=facts.counts.candidates_suppressed,
            suppressed_reasons=[list(item) for item in facts.counts.suppressed_reasons],
        ),
        advanced=facts.advanced,
    )


def _external_url_snapshot_url_configured(
    repository: ProductRepository, source_id: str,
) -> bool:
    """Side-effect-free mirror of `_validate_monitor_source`'s own
    readiness check, reused for the pre-start "Ready"/"Needs attention"
    health fact instead of re-deriving new copy."""

    configuration = repository.get_source_provider_configuration(source_id)
    if configuration is None or configuration.provider_key != "external_url":
        return False
    url = configuration.safe_config_preview.get("url")
    return bool(url) and url != "not_configured"


async def _unified_observation_facts(
    stream_id: str, configuration: StreamLivePlaybackConfig,
) -> unified_status.ObservationPanelFacts:
    """Side-effect-free composition of the unified status for whichever
    lane this Stream actually uses. Never starts a camera, model, monitor,
    or session -- only reads facts each existing runtime already exposes."""

    repository = get_repository()
    playback = repository.get_stream_playback_status(stream_id)
    lane = unified_status.resolve_observation_runtime(configuration)

    if lane == unified_status.RUNTIME_KIND_CAMERA_NODE:
        session_status = get_observation_engine_session_manager().status(stream_id)
        return unified_status.camera_node_facts(
            session_status=session_status, config=configuration, playback=playback,
        )

    if lane == unified_status.RUNTIME_KIND_LIVE_MONITORING:
        policy = repository.get_stream_monitoring_policy(stream_id)
        runtime = repository.get_stream_runtime_status(stream_id)
        health = repository.get_stream_camera_health(stream_id)
        return unified_status.live_monitoring_facts(
            policy=policy, runtime=runtime,
            health=health.health if health is not None else None,
            playback=playback,
        )

    if lane == unified_status.RUNTIME_KIND_SNAPSHOT_MONITOR:
        monitor_state = await get_source_monitor_manager().status(stream_id)
        monitor = _monitor_status_response(monitor_state) if monitor_state is not None else None
        url_configured = _external_url_snapshot_url_configured(repository, configuration.source_id)
        return unified_status.snapshot_monitor_facts(
            monitor=monitor, url_configured=url_configured, playback=playback,
        )

    return unified_status.unavailable_facts(config=configuration, playback=playback)


@app.post(
    "/api/streams/{stream_id}/observation/start",
    response_model=ObservationSessionStatusResponse,
)
async def start_stream_observation(stream_id: str) -> ObservationSessionStatusResponse:
    """Unified Start observing (Unified Observation Experience v1): one
    product action for every currently-supported Stream type, each routed
    to its own existing, unmodified runtime.

    - A paired Camera Node Stream reuses the accepted Observation Engine
      start path unchanged (Product requirement 1).
    - A Stream configured for an existing backend-owned live-video kind
      (RTSP, Linux local USB, Windows DirectShow) arms the existing durable
      monitoring policy -- the same action "Enable monitoring" already
      performs -- instead of a second monitoring worker.
    - A remaining `external_url` Stream starts the existing Snapshot Source
      monitor.
    - A Stream with no integrated observation runtime reports an honest
      unavailable status rather than scaffolding fake support.

    Always 200 with an honest status; invalid configuration is rejected
    safely (never arms a policy or worker that cannot start) instead of
    raising."""

    repository = get_repository()
    configuration = _stream_live_playback_config_or_404(stream_id, require_active_source=True)
    lane = unified_status.resolve_observation_runtime(configuration)

    if lane == unified_status.RUNTIME_KIND_CAMERA_NODE:
        regions = repository.stream_privacy_ignore_regions(stream_id)
        status = get_observation_engine_session_manager().start(
            stream_id, configuration, privacy_ignore_regions=regions,
        )
        facts = unified_status.camera_node_facts(
            session_status=status, config=configuration,
            playback=repository.get_stream_playback_status(stream_id),
        )
        return _observation_panel_response(stream_id, facts)

    if lane == unified_status.RUNTIME_KIND_LIVE_MONITORING:
        playback = repository.get_stream_playback_status(stream_id)
        if playback is None or playback.status != StreamPlaybackStatusValue.live_ready:
            # Reject invalid configuration safely: never arm a policy that
            # cannot actually start.
            facts = unified_status.live_monitoring_facts(
                policy=repository.get_stream_monitoring_policy(stream_id),
                runtime=repository.get_stream_runtime_status(stream_id),
                health=repository.get_stream_camera_health(stream_id).health,
                playback=playback,
            )
            return _observation_panel_response(stream_id, facts)
        mutation = await update_stream_monitoring_policy(
            stream_id,
            StreamMonitoringPolicyUpdate(
                enabled=True, idempotency_key=f"observation-start-{uuid.uuid4().hex}",
            ),
        )
        facts = unified_status.live_monitoring_facts(
            policy=mutation.policy, runtime=mutation.runtime,
            health=repository.get_stream_camera_health(stream_id).health,
            playback=playback,
        )
        return _observation_panel_response(stream_id, facts)

    if lane == unified_status.RUNTIME_KIND_SNAPSHOT_MONITOR:
        playback = repository.get_stream_playback_status(stream_id)
        url_configured = _external_url_snapshot_url_configured(repository, configuration.source_id)
        try:
            monitor = await start_stream_monitor(stream_id)
        except HTTPException as error:
            # Reject invalid configuration safely instead of a raw 400,
            # while preserving that route's own sanitized reason.
            reason = str(error.detail)
            facts = unified_status.snapshot_monitor_facts(
                monitor=None, url_configured=url_configured, playback=playback,
            )
            facts = replace(facts, message=reason, camera_message=reason, engine_message=reason)
            return _observation_panel_response(stream_id, facts)
        facts = unified_status.snapshot_monitor_facts(
            monitor=monitor, url_configured=url_configured, playback=playback,
        )
        return _observation_panel_response(stream_id, facts)

    facts = unified_status.unavailable_facts(
        config=configuration, playback=repository.get_stream_playback_status(stream_id),
    )
    return _observation_panel_response(stream_id, facts)


@app.post(
    "/api/streams/{stream_id}/observation/stop",
    response_model=ObservationSessionStatusResponse,
)
async def stop_stream_observation(stream_id: str) -> ObservationSessionStatusResponse:
    """Unified Stop observing: works for every integrated runtime, is
    bounded, releases that runtime's own resources, and never deletes
    evidence or changes reviewed/candidate records. A user never needs to
    know which runtime they are stopping.

    - Camera Node: the accepted engine's own kill switch, unchanged --
      candidate authority always reverts to shadow.
    - Live monitoring: disarms the existing durable monitoring policy, the
      same action "Disable monitoring" already performs.
    - Snapshot monitor: stops the existing Snapshot Source monitor.
    - No integrated runtime: a clean no-op, honestly reported.

    Idempotent: stopping an already-stopped Stream is always a safe no-op."""

    repository = get_repository()
    configuration = _stream_live_playback_config_or_404(stream_id)
    lane = unified_status.resolve_observation_runtime(configuration)

    if lane == unified_status.RUNTIME_KIND_CAMERA_NODE:
        status = get_observation_engine_session_manager().stop(stream_id)
        facts = unified_status.camera_node_facts(
            session_status=status, config=configuration,
            playback=repository.get_stream_playback_status(stream_id),
        )
        return _observation_panel_response(stream_id, facts)

    if lane == unified_status.RUNTIME_KIND_LIVE_MONITORING:
        mutation = await update_stream_monitoring_policy(
            stream_id,
            StreamMonitoringPolicyUpdate(
                enabled=False, idempotency_key=f"observation-stop-{uuid.uuid4().hex}",
            ),
        )
        facts = unified_status.live_monitoring_facts(
            policy=mutation.policy, runtime=mutation.runtime,
            health=repository.get_stream_camera_health(stream_id).health,
            playback=repository.get_stream_playback_status(stream_id),
        )
        return _observation_panel_response(stream_id, facts)

    if lane == unified_status.RUNTIME_KIND_SNAPSHOT_MONITOR:
        monitor = await stop_stream_monitor(stream_id)
        playback = repository.get_stream_playback_status(stream_id)
        url_configured = _external_url_snapshot_url_configured(repository, configuration.source_id)
        facts = unified_status.snapshot_monitor_facts(
            monitor=monitor, url_configured=url_configured, playback=playback,
        )
        return _observation_panel_response(stream_id, facts)

    facts = unified_status.unavailable_facts(
        config=configuration, playback=repository.get_stream_playback_status(stream_id),
    )
    return _observation_panel_response(stream_id, facts)


@app.get(
    "/api/streams/{stream_id}/observation/status",
    response_model=ObservationSessionStatusResponse,
)
async def get_stream_observation_status(stream_id: str) -> ObservationSessionStatusResponse:
    """Side-effect-free: never starts a camera, model, monitor, or session,
    regardless of which existing runtime this Stream uses."""

    configuration = _stream_live_playback_config_or_404(stream_id)
    facts = await _unified_observation_facts(stream_id, configuration)
    return _observation_panel_response(stream_id, facts)


def _counterfactual_accounting_response(accounting) -> CounterfactualLedgerAccountingResponse:
    return CounterfactualLedgerAccountingResponse(
        retained_count=accounting.retained_count,
        evicted_count=accounting.evicted_count,
        recorded_count=accounting.recorded_count,
        oldest_retained_offset_ms=accounting.oldest_retained_offset_ms,
        newest_retained_offset_ms=accounting.newest_retained_offset_ms,
    )


def _counterfactual_confidence_response(evidence) -> CounterfactualConfidenceSummaryResponse:
    return CounterfactualConfidenceSummaryResponse(
        detection_count=evidence.detection_count if evidence is not None else 0,
        max_confidence=evidence.max_confidence if evidence is not None else None,
        strong_detection_count=evidence.strong_detection_count if evidence is not None else None,
    )


def _counterfactual_window_response(window, attribution) -> CounterfactualWindowResponse:
    """Wrap the pure `counterfactual_lineage.CounterfactualWindowResult` (and
    its own `classify_rejection_attribution` read) in the product wire
    contract -- the one place engine-side facts cross into API vocabulary,
    mirroring `_observation_panel_response`'s own established role."""

    return CounterfactualWindowResponse(
        stream_id=window.stream_id,
        start_offset_ms=window.start_offset_ms,
        end_offset_ms=window.end_offset_ms,
        roi=list(window.roi) if window.roi is not None else None,
        raw_detections=[
            CounterfactualRawDetectionResponse(
                source_offset_ms=item.source_offset_ms,
                captured_at=item.captured_at,
                frame_id=item.frame_id,
                detector_id=item.detector_id,
                provider_id=item.provider_id,
                broad_class=item.broad_class,
                is_animal=item.is_animal,
                confidence=item.confidence,
                bounding_box=list(item.bounding_box) if item.bounding_box is not None else None,
            )
            for item in window.raw_detections
        ],
        track_generations=[
            CounterfactualTrackGenerationResponse(
                generation_id=item.generation_id,
                broad_class=item.broad_class,
                track_ids=list(item.track_ids),
                start_offset_ms=item.start_offset_ms,
                end_offset_ms=item.end_offset_ms,
                start_bounding_box=list(item.start_bounding_box),
                end_bounding_box=list(item.end_bounding_box),
                geometry_envelope=list(item.geometry_envelope),
                confirmed=item.confirmed,
                terminal_reason=item.terminal_reason,
                terminal_geometry_source=item.terminal_geometry_source,
                confidence_evidence=_counterfactual_confidence_response(item.confidence_evidence),
            )
            for item in window.track_generations
        ],
        proposal_outcomes=[
            CounterfactualProposalOutcomeResponse(
                proposal_id=item.proposal_id,
                broad_class=item.broad_class,
                zone_id=item.zone_id,
                start_offset_ms=item.start_offset_ms,
                end_offset_ms=item.end_offset_ms,
                constituent_generation_ids=list(item.constituent_generation_ids),
                outcome=item.outcome,
                reason=item.reason,
                admitted=item.admitted,
                visit_id=item.visit_id,
                decided_at=item.decided_at,
            )
            for item in window.proposal_outcomes
        ],
        raw_detection_count_in_roi=len(window.raw_detections_in_roi),
        track_generation_count_in_roi=len(window.track_generations_in_roi),
        coverage=CounterfactualCoverageResponse(
            session_first_offset_ms=window.coverage.session_first_offset_ms,
            session_last_offset_ms=window.coverage.session_last_offset_ms,
            raw_detections=_counterfactual_accounting_response(window.coverage.raw_detection_retention),
            track_generations=_counterfactual_accounting_response(window.coverage.track_generation_retention),
            proposal_outcomes=_counterfactual_accounting_response(window.coverage.proposal_outcome_retention),
        ),
        attribution=attribution.attribution,
        attribution_reason=attribution.reason,
    )


@app.get(
    "/api/streams/{stream_id}/observation/counterfactual",
    response_model=CounterfactualWindowResponse,
)
async def get_stream_observation_counterfactual(
    stream_id: str,
    start_offset_ms: int = Query(..., ge=0),
    end_offset_ms: int = Query(..., ge=0),
    roi_left: float | None = Query(None, ge=0.0, le=1.0),
    roi_top: float | None = Query(None, ge=0.0, le=1.0),
    roi_right: float | None = Query(None, ge=0.0, le=1.0),
    roi_bottom: float | None = Query(None, ge=0.0, le=1.0),
) -> CounterfactualWindowResponse:
    """Rejected / Suppressed Detection Attribution v1 (see
    docs/rejected-detection-attribution-contract.md): what happened around
    one source-relative time window -- and, optionally, one normalized
    region of interest (`roi_left/top/right/bottom`, all four or none) -- on
    the current or most recently stopped Observation Engine session for
    this Stream. Side-effect-free: never starts a session, never creates
    evidence, never writes truth. Direct database archaeology is not
    required for this diagnostic workflow.

    404 for an unknown Stream (matching `/observation/status`); a known
    Stream that has never started an Observation Engine session in this
    process returns an honest, empty, `insufficient_counterfactual_lineage`
    result rather than a 404 -- "never started" and "started but nothing
    here" are different, both real, facts.
    """

    _stream_live_playback_config_or_404(stream_id)
    if end_offset_ms < start_offset_ms:
        raise HTTPException(status_code=400, detail="end_offset_ms must not precede start_offset_ms.")
    roi_values = (roi_left, roi_top, roi_right, roi_bottom)
    if any(value is not None for value in roi_values) and any(value is None for value in roi_values):
        raise HTTPException(status_code=400, detail="Supply all four roi_* bounds, or none.")
    roi = (roi_left, roi_top, roi_right, roi_bottom) if roi_left is not None else None
    if roi is not None and (roi[0] >= roi[2] or roi[1] >= roi[3]):
        raise HTTPException(status_code=400, detail="roi bounds must satisfy left < right and top < bottom.")

    window = get_observation_engine_session_manager().counterfactual_query(
        stream_id, start_offset_ms=start_offset_ms, end_offset_ms=end_offset_ms, roi=roi,
    )
    if window is None:
        empty_accounting = CounterfactualLedgerAccountingResponse(
            retained_count=0, evicted_count=0, recorded_count=0,
        )
        return CounterfactualWindowResponse(
            stream_id=stream_id, start_offset_ms=start_offset_ms, end_offset_ms=end_offset_ms,
            roi=list(roi) if roi is not None else None,
            raw_detections=[], track_generations=[], proposal_outcomes=[],
            raw_detection_count_in_roi=0, track_generation_count_in_roi=0,
            coverage=CounterfactualCoverageResponse(
                raw_detections=empty_accounting, track_generations=empty_accounting,
                proposal_outcomes=empty_accounting,
            ),
            attribution="insufficient_counterfactual_lineage",
            attribution_reason="no_observation_engine_session_has_run_for_this_stream_in_this_process",
        )
    attribution = classify_rejection_attribution(window)
    return _counterfactual_window_response(window, attribution)


@app.get("/api/streams/{stream_id}/live-session/current-frame")
async def get_stream_live_camera_current_frame(stream_id: str) -> Response:
    """Return one cached camera frame without opening a camera or monitor.

    This is deliberately a still-image read: a browser can refresh it at a
    bounded cadence while the existing app-owned session remains the sole
    camera owner. It never starts monitoring, writes media, or creates
    activity/review data.
    """

    _stream_live_playback_config_or_404(stream_id, require_active_source=True)
    snapshot = (
        _live_camera_session_manager.status(stream_id)
        if _live_camera_session_manager is not None
        else None
    )
    if snapshot is None or snapshot.status not in {"starting", "running"}:
        raise HTTPException(
            status_code=409,
            detail="Camera session is not active; viewing never starts monitoring.",
        )

    frame = live_frame_cache.get_last_frame(stream_id)
    if frame is None:
        raise HTTPException(
            status_code=404,
            detail="No camera frame is available yet.",
        )

    decoded = cv2.imdecode(np.frombuffer(frame.frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise HTTPException(status_code=502, detail="The latest camera frame could not be decoded.")
    height, width = decoded.shape[:2]
    age_ms = frame.age_ms()
    state = "live" if age_ms <= 2_500 else "delayed" if age_ms <= 10_000 else "stale"
    return Response(
        content=frame.frame_bytes,
        media_type=frame.content_type,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-MockingBird-Frame-Sequence": str(frame.sequence),
            "X-MockingBird-Frame-Captured-At": frame.captured_at.isoformat(),
            "X-MockingBird-Frame-Age-Ms": str(age_ms),
            "X-MockingBird-Frame-Width": str(width),
            "X-MockingBird-Frame-Height": str(height),
            "X-MockingBird-Frame-State": state,
        },
    )


@app.get(
    "/api/streams/{stream_id}/live-session/status",
    response_model=LiveCameraSessionStatusResponse,
)
async def get_stream_live_camera_session_status(
    stream_id: str,
) -> LiveCameraSessionStatusResponse:
    configuration = _stream_live_playback_config_or_404(stream_id)
    snapshot = (
        _live_camera_session_manager.status(stream_id)
        if _live_camera_session_manager is not None
        else None
    )
    return _live_camera_session_response(snapshot, configuration)


def _overview_preview_configuration_or_409(stream_id: str) -> StreamLivePlaybackConfig:
    configuration = _stream_live_playback_config_or_404(
        stream_id,
        require_active_source=True,
    )
    if configuration.live_stream_type not in live_camera_session.SUPPORTED_SESSION_TYPES:
        raise HTTPException(
            status_code=409,
            detail="Preview unavailable for this camera. Open Stream Detail for setup guidance.",
        )
    try:
        _validate_live_camera_session_config(configuration)
    except HTTPException as error:
        if error.status_code == 404:
            raise
        raise HTTPException(
            status_code=409,
            detail="Preview unavailable for this camera. Open Stream Detail for setup guidance.",
        ) from None
    return configuration


@app.post(
    "/api/streams/{stream_id}/live-preview/open",
    response_model=LivePreviewLeaseResponse,
)
async def open_stream_live_preview(
    stream_id: str,
    payload: LivePreviewLeaseRequest,
) -> LivePreviewLeaseResponse:
    """Open one bounded overview-owned view without changing monitoring intent."""

    configuration = _overview_preview_configuration_or_409(stream_id)
    camera_manager = get_live_camera_session_manager()
    existing_snapshot = camera_manager.status(stream_id)
    session_is_active = bool(
        existing_snapshot and existing_snapshot.status in {"starting", "running"}
    )
    preview_manager = get_live_preview_lease_manager()
    decision = preview_manager.acquire(
        owner_id=payload.owner_id,
        stream_id=stream_id,
        backend_session_active=session_is_active,
    )
    if decision.status == "limit_reached":
        return LivePreviewLeaseResponse(
            stream_id=stream_id,
            owner_id=payload.owner_id,
            status=LivePreviewLeaseStatus.limit_reached,
            max_active_previews=preview_manager.max_previews_per_owner,
            effective_limit=decision.effective_limit,
            message=decision.message,
        )

    if decision.should_start_session:
        try:
            started_snapshot = camera_manager.start(configuration)
        except (OSError, ValueError):
            preview_manager.abandon(owner_id=payload.owner_id, stream_id=stream_id)
            raise HTTPException(
                status_code=502,
                detail="Camera unavailable. The latest activity remains available for review.",
            ) from None
        if started_snapshot.status == "paused":
            # Observation Engine already owns this physical camera (see
            # `LiveCameraSessionManager.pause_for_observation`); `start()`
            # deliberately refused to fight it for the same Camera Node
            # capture and returned the existing paused session unchanged.
            # Report that honestly instead of claiming a live preview that
            # cannot actually stream right now.
            preview_manager.abandon(owner_id=payload.owner_id, stream_id=stream_id)
            return LivePreviewLeaseResponse(
                stream_id=stream_id,
                owner_id=payload.owner_id,
                status=LivePreviewLeaseStatus.unavailable,
                max_active_previews=preview_manager.max_previews_per_owner,
                effective_limit=decision.effective_limit,
                message="Live preview is paused while Observation Engine is watching this camera.",
            )

    return LivePreviewLeaseResponse(
        stream_id=stream_id,
        owner_id=payload.owner_id,
        status=LivePreviewLeaseStatus.live,
        preview_url=f"/api/streams/{stream_id}/live-session/mjpeg",
        expires_at=decision.lease.expires_at if decision.lease is not None else None,
        max_active_previews=preview_manager.max_previews_per_owner,
        effective_limit=decision.effective_limit,
        message="Live preview is active. Viewing does not enable monitoring or save media.",
    )


@app.post(
    "/api/streams/{stream_id}/live-preview/close",
    response_model=LivePreviewReleaseResponse,
)
async def close_stream_live_preview(
    stream_id: str,
    payload: LivePreviewLeaseRequest,
) -> LivePreviewReleaseResponse:
    """Release one overview tile while preserving any existing monitor ownership."""

    # Resolve the Stream first so an arbitrary id never reaches runtime ownership.
    _stream_live_playback_config_or_404(stream_id)
    release = get_live_preview_lease_manager().release(
        owner_id=payload.owner_id,
        stream_id=stream_id,
    )
    if release.should_stop_session:
        _release_overview_started_session(stream_id)
    return LivePreviewReleaseResponse(
        stream_id=stream_id,
        owner_id=payload.owner_id,
        released=release.released,
        message=(
            "Live preview stopped. Monitoring settings are unchanged."
            if release.released
            else "Live preview was already released. Monitoring settings are unchanged."
        ),
    )


@app.get(
    "/api/streams/{stream_id}/live-session/diagnostics",
    response_model=LiveCameraSessionDiagnosticsResponse,
)
async def get_stream_live_camera_session_diagnostics(
    stream_id: str,
) -> LiveCameraSessionDiagnosticsResponse:
    _stream_live_playback_config_or_404(stream_id)
    snapshot = (
        _live_camera_session_manager.status(stream_id)
        if _live_camera_session_manager is not None
        else None
    )
    return LiveCameraSessionDiagnosticsResponse(
        stream_id=stream_id,
        diagnostic_events=(snapshot.diagnostic_events if snapshot is not None else []),
        diagnostic_events_truncated=(
            snapshot.diagnostic_events_truncated if snapshot is not None else False
        ),
        creates_truth=False,
    )


@app.get("/api/streams/{stream_id}/live-session/mjpeg")
async def get_stream_live_camera_session_mjpeg(stream_id: str) -> StreamingResponse:
    configuration = _stream_live_playback_config_or_404(
        stream_id,
        require_active_source=True,
    )
    _validate_live_camera_session_config(configuration)
    snapshot = get_live_camera_session_manager().status(stream_id)
    if snapshot is None or snapshot.status not in {"starting", "running"}:
        raise HTTPException(
            status_code=409,
            detail="Start camera session before opening live view.",
        )
    return StreamingResponse(
        get_live_camera_session_manager().iter_mjpeg(stream_id),
        media_type=(
            f"multipart/x-mixed-replace; boundary={live_camera_session.MJPEG_BOUNDARY}"
        ),
    )


@app.get(
    "/api/local-cameras/windows",
    response_model=WindowsCameraDiscoveryResponse,
)
async def discover_windows_cameras() -> WindowsCameraDiscoveryResponse:
    """List local Windows webcams without opening or recording from them."""

    if not sys.platform.startswith("win"):
        return WindowsCameraDiscoveryResponse(
            status="unsupported_platform",
            message="Automatic camera detection is available when MockingBird runs on Windows.",
        )
    if not windows_camera_bridge.is_windows_ffmpeg_available():
        return WindowsCameraDiscoveryResponse(
            status="ffmpeg_missing",
            message="Camera detection needs FFmpeg. Install FFmpeg, then retry.",
        )
    try:
        devices = windows_camera_bridge.list_windows_dshow_video_devices()
    except subprocess.TimeoutExpired:
        return WindowsCameraDiscoveryResponse(
            status="failed",
            message="Camera detection timed out. Check the camera connection and retry.",
        )
    except OSError:
        return WindowsCameraDiscoveryResponse(
            status="failed",
            message="Camera detection could not start. Check FFmpeg and retry.",
        )
    if not devices:
        return WindowsCameraDiscoveryResponse(
            status="no_devices",
            message=(
                "No Windows cameras were found. Connect a camera, close other camera apps, "
                "and retry."
            ),
        )
    return WindowsCameraDiscoveryResponse(
        status="available",
        devices=devices,
        message=(
            f"Found {len(devices)} camera."
            if len(devices) == 1
            else f"Found {len(devices)} cameras."
        ),
    )


@app.post(
    "/api/streams/{stream_id}/camera-controls/open",
    response_model=WindowsCameraControlsResponse,
)
async def open_stream_windows_camera_controls(
    stream_id: str,
) -> WindowsCameraControlsResponse:
    """Open real DirectShow controls only after an explicit local user action."""

    configuration = _stream_live_playback_config_or_404(
        stream_id,
        require_active_source=True,
    )
    common = {
        "stream_id": stream_id,
        "source_id": configuration.source_id,
    }
    if (
        configuration.live_stream_type
        != windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE
    ):
        return WindowsCameraControlsResponse(
            **common,
            status="unsupported_platform",
            message=(
                "This Stream does not support an interactive Windows DirectShow window."
            ),
        )

    snapshot = (
        _live_camera_session_manager.status(stream_id)
        if _live_camera_session_manager is not None
        else None
    )
    source_monitor_state = (
        await _source_monitor_manager.status(stream_id)
        if _source_monitor_manager is not None
        else None
    )
    live_monitor_running = snapshot is not None and snapshot.monitor_running
    source_monitor_running = (
        source_monitor_state is not None
        and source_monitor_state.status in {"starting", "monitoring"}
    )
    if live_monitor_running or source_monitor_running:
        return WindowsCameraControlsResponse(
            **common,
            status="monitor_running",
            message="Stop monitoring before opening native camera controls.",
        )
    if snapshot is not None and snapshot.status in {"starting", "running", "stopping"}:
        return WindowsCameraControlsResponse(
            **common,
            status="camera_running",
            message="Stop the camera before opening native camera controls.",
        )

    controls_status = windows_camera_bridge.windows_camera_controls_status(
        camera_name=configuration.windows_camera_name,
        ffmpeg_binary_path=configuration.windows_ffmpeg_binary_path,
    )
    if controls_status == "camera_name_missing":
        return WindowsCameraControlsResponse(
            **common,
            status="camera_not_configured",
            message="Configure a DirectShow camera name before opening native controls.",
        )
    if controls_status == "ffmpeg_missing":
        return WindowsCameraControlsResponse(
            **common,
            status="ffmpeg_missing",
            message="Configure Windows ffmpeg.exe before opening native controls.",
        )
    if controls_status == "unsupported_platform":
        return WindowsCameraControlsResponse(
            **common,
            status="unsupported_platform",
            message=(
                "This host configuration does not support an interactive DirectShow window."
            ),
        )
    if controls_status != "available":
        return WindowsCameraControlsResponse(
            **common,
            status="controls_unavailable",
            message="Native Windows camera controls could not be launched on this host.",
        )

    try:
        completed = await asyncio.to_thread(
            windows_camera_bridge.launch_windows_dshow_camera_controls,
            configuration.windows_camera_name or "",
            ffmpeg_binary_path=configuration.windows_ffmpeg_binary_path,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return WindowsCameraControlsResponse(
            **common,
            status="launch_failed",
            message="Native camera controls could not be launched.",
        )
    if completed.returncode != 0:
        return WindowsCameraControlsResponse(
            **common,
            status="launch_failed",
            message="Native camera controls could not be launched.",
        )
    return WindowsCameraControlsResponse(
        **common,
        status="launched",
        message=(
            "Native Windows camera controls were launched. Adjust exposure, gain, or "
            "low-light settings in the camera driver, close the native window, then "
            "restart the camera and capture a test frame. MockingBird cannot read or "
            "persist these driver-managed values."
        ),
        warnings=[
            "Camera-driver settings may reset after reconnecting; verify the daylight image."
        ],
    )


@app.get("/api/streams/{stream_id}/live/rtsp-mjpeg")
async def get_stream_rtsp_mjpeg_bridge(stream_id: str) -> StreamingResponse:
    configuration = _stream_live_playback_config_or_404(
        stream_id,
        require_active_source=True,
    )
    _validate_live_camera_session_config(configuration, expected_kind="rtsp")
    try:
        get_live_camera_session_manager().start(configuration)
    except (OSError, ValueError):
        raise HTTPException(
            status_code=502, detail="RTSP live view failed to start."
        ) from None

    return StreamingResponse(
        get_live_camera_session_manager().iter_mjpeg(stream_id),
        media_type=f"multipart/x-mixed-replace; boundary={live_camera_session.MJPEG_BOUNDARY}",
    )


@app.get("/api/streams/{stream_id}/live/local-mjpeg")
async def get_stream_local_mjpeg_bridge(stream_id: str) -> StreamingResponse:
    configuration = _stream_live_playback_config_or_404(
        stream_id,
        require_active_source=True,
    )
    _validate_live_camera_session_config(
        configuration,
        expected_kind=local_camera_bridge.LOCAL_USB_STREAM_TYPE,
    )
    try:
        get_live_camera_session_manager().start(configuration)
    except (OSError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Local camera device unavailable or playback failed.",
        ) from None

    return StreamingResponse(
        get_live_camera_session_manager().iter_mjpeg(stream_id),
        media_type=(
            f"multipart/x-mixed-replace; boundary={live_camera_session.MJPEG_BOUNDARY}"
        ),
    )


@app.get("/api/streams/{stream_id}/live/windows-dshow-mjpeg")
async def get_stream_windows_dshow_mjpeg_bridge(stream_id: str) -> StreamingResponse:
    configuration = _stream_live_playback_config_or_404(
        stream_id,
        require_active_source=True,
    )
    _validate_live_camera_session_config(
        configuration,
        expected_kind=windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE,
    )
    try:
        get_live_camera_session_manager().start(configuration)
    except (OSError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Windows DirectShow camera unavailable or playback failed.",
        ) from None

    return StreamingResponse(
        get_live_camera_session_manager().iter_mjpeg(stream_id),
        media_type=(
            f"multipart/x-mixed-replace; boundary={live_camera_session.MJPEG_BOUNDARY}"
        ),
    )


@app.post(
    "/api/streams/{stream_id}/local-camera/capture-frame",
    response_model=LocalCameraFrameCaptureResponse,
)
async def capture_stream_local_camera_frame(
    stream_id: str,
) -> LocalCameraFrameCaptureResponse:
    repository = get_repository()
    configuration = _stream_live_playback_config_or_404(
        stream_id,
        require_active_source=True,
    )

    common = {
        "stream_id": configuration.stream_id,
        "source_id": configuration.source_id,
        "creates_truth": False,
        "creates_event": False,
        "creates_visit": False,
        "creates_export": False,
    }
    if configuration.provider_key != "local_usb":
        return LocalCameraFrameCaptureResponse(
            **common,
            status="unsupported",
            message="Capture frame requires a local camera Source provider.",
            warnings=["This Stream is not configured for local camera playback."],
        )

    session_snapshot = get_live_camera_session_manager().status(configuration.stream_id)
    session_running = session_snapshot is not None and session_snapshot.status in {
        "starting",
        "running",
    }
    if session_running and configuration.live_stream_type in {
        local_camera_bridge.LOCAL_USB_STREAM_TYPE,
        windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE,
    }:
        # The active session owns the camera process; capture must reuse its cache.
        cached_frame = get_live_camera_session_manager().capture_latest_frame(
            configuration.stream_id,
        )
        if cached_frame is None:
            return LocalCameraFrameCaptureResponse(
                **common,
                status="unavailable",
                message="No fresh session frame available; camera session is still running.",
                capture_source="unavailable",
                warnings=[
                    "MockingBird will not start a second camera process while the session is running."
                ],
            )
        playback_type = configuration.live_stream_type
        camera_label = (
            configuration.windows_camera_name
            if playback_type == windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE
            else configuration.local_camera_device
        )
        try:
            media_asset = repository.create_local_camera_frame_media_asset(
                source_id=configuration.source_id,
                stream_id=configuration.stream_id,
                content=cached_frame.frame_bytes,
                captured_at=cached_frame.captured_at,
                playback_type=playback_type,
                camera_label=camera_label,
            )
        except ValueError as error:
            raise _media_import_error(error) from error

        return LocalCameraFrameCaptureResponse(
            **common,
            media_asset_id=media_asset.id,
            status="saved",
            message=(
                "Captured current frame; camera and monitoring are still running."
                if session_snapshot.monitor_running
                else "Captured current frame from the running camera session."
            ),
            file_name=media_asset.filename,
            relative_path=media_asset.filename,
            bytes_written=media_asset.file_size_bytes,
            content_type=media_asset.content_type,
            capture_source="live_camera_session",
            live_frame_age_ms=cached_frame.age_ms(),
        )

    if session_running:
        return LocalCameraFrameCaptureResponse(
            **common,
            status="unavailable",
            message="No fresh session frame available; camera session is still running.",
            capture_source="unavailable",
            warnings=[
                "MockingBird will not start a second camera process while the session is running."
            ],
        )

    if (
        configuration.live_stream_type
        == windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE
    ):
        bridge_status = windows_camera_bridge.windows_camera_status(
            camera_name=configuration.windows_camera_name,
            ffmpeg_binary_path=configuration.windows_ffmpeg_binary_path,
        )
        if bridge_status == "camera_name_missing":
            return LocalCameraFrameCaptureResponse(
                **common,
                status="camera_not_configured",
                message="Choose a Windows DirectShow camera name before capture.",
                warnings=[
                    "Use Detect cameras in Cameras/Streams, then choose the connected Windows "
                    "webcam."
                ],
            )
        if bridge_status == "unsupported_host":
            return LocalCameraFrameCaptureResponse(
                **common,
                status="unsupported",
                message=(
                    "Windows DirectShow requires Windows ffmpeg.exe or running the API on Windows."
                ),
                warnings=[
                    "If the API runs in WSL, configure a Windows ffmpeg.exe path."
                ],
            )
        if bridge_status == "ffmpeg_missing":
            return LocalCameraFrameCaptureResponse(
                **common,
                status="ffmpeg_missing",
                message="Windows DirectShow capture unavailable: ffmpeg not found.",
            )
        try:
            frame = windows_camera_bridge.capture_windows_dshow_frame(
                configuration.windows_camera_name or "",
                ffmpeg_binary_path=configuration.windows_ffmpeg_binary_path,
                input_format=configuration.input_format,
                video_size=configuration.camera_video_size,
                framerate=configuration.camera_framerate,
            )
        except (OSError, ValueError):
            return LocalCameraFrameCaptureResponse(
                **common,
                status="capture_failed",
                message=(
                    "Camera is busy or did not return a frame. Close other camera apps, "
                    "or open Live view until a frame appears and retry capture."
                ),
                capture_source="one_shot_ffmpeg",
                warnings=[
                    "Check the camera name and confirm Windows privacy permissions."
                ],
            )
        playback_type = windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE
        camera_label = configuration.windows_camera_name
    elif configuration.live_stream_type == local_camera_bridge.LOCAL_USB_STREAM_TYPE:
        bridge_status = local_camera_bridge.local_camera_status(
            device=configuration.local_camera_device,
            camera_format=configuration.local_camera_format,
        )
        if bridge_status == "device_missing":
            return LocalCameraFrameCaptureResponse(
                **common,
                status="camera_not_configured",
                message="Choose a local camera device such as /dev/video0 before capture.",
            )
        if bridge_status in {"invalid_device", "unsupported_platform"}:
            return LocalCameraFrameCaptureResponse(
                **common,
                status="unsupported",
                message="Local camera capture requires a supported Linux /dev/video* device.",
            )
        if bridge_status == "ffmpeg_missing":
            return LocalCameraFrameCaptureResponse(
                **common,
                status="ffmpeg_missing",
                message="Local camera capture unavailable: ffmpeg not found.",
            )
        try:
            frame = local_camera_bridge.capture_local_camera_frame(
                configuration.local_camera_device or "",
                camera_format=configuration.local_camera_format,
                input_format=configuration.input_format,
                video_size=configuration.camera_video_size,
                input_frame_rate=configuration.camera_framerate,
            )
        except (OSError, ValueError):
            return LocalCameraFrameCaptureResponse(
                **common,
                status="capture_failed",
                message=(
                    "Camera is busy or did not return a frame. Close other camera apps, "
                    "or open Live view until a frame appears and retry capture."
                ),
                capture_source="one_shot_ffmpeg",
                warnings=["Confirm the local camera device path is available."],
            )
        playback_type = local_camera_bridge.LOCAL_USB_STREAM_TYPE
        camera_label = configuration.local_camera_device
    else:
        return LocalCameraFrameCaptureResponse(
            **common,
            status="unsupported",
            message="Capture frame is available only for local_usb and windows_dshow playback.",
        )

    try:
        media_asset = repository.create_local_camera_frame_media_asset(
            source_id=configuration.source_id,
            stream_id=configuration.stream_id,
            content=frame,
            captured_at=datetime.now(UTC),
            playback_type=playback_type,
            camera_label=camera_label,
        )
    except ValueError as error:
        raise _media_import_error(error) from error

    return LocalCameraFrameCaptureResponse(
        **common,
        media_asset_id=media_asset.id,
        status="saved",
        message=(
            "Saved one local camera frame directly because Live view was not streaming. "
            "It will not appear in Bird Log until you create/review activity."
        ),
        file_name=media_asset.filename,
        relative_path=media_asset.filename,
        bytes_written=media_asset.file_size_bytes,
        content_type=media_asset.content_type,
        capture_source="one_shot_ffmpeg",
    )


@app.get("/api/streams/{stream_id}/zones", response_model=list[Zone])
async def list_stream_zones(stream_id: str) -> list[Zone]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return repository.zones_for_stream(stream_id)


@app.get("/api/streams/{stream_id}/events", response_model=list[Event])
async def list_stream_events(
    stream_id: str,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Event]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return repository.events_for_stream(stream_id, limit=limit)


@app.get("/api/streams/{stream_id}/visits", response_model=list[StreamVisitSummary])
async def list_stream_recent_visits(
    stream_id: str,
    limit: int = Query(default=12, ge=1, le=50),
    review_status: ReviewStatus | None = None,
    zone_id: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[StreamVisitSummary]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    if zone_id is not None:
        zone = repository.get_zone(zone_id)
        if zone is None:
            raise _not_found("Zone", zone_id)
        if zone.stream_id != stream.id:
            raise HTTPException(status_code=400, detail="Zone does not belong to this Stream.")
    if end_at is not None and start_at is not None and end_at < start_at:
        raise HTTPException(status_code=400, detail="End date must not be before start date.")

    # This read stays bounded and Stream-scoped; detail evidence remains lazy.
    return repository.recent_visits_for_stream(
        stream.id,
        limit=limit,
        review_status=review_status,
        zone_id=zone_id,
        start_at=start_at,
        end_at=end_at,
    )


@app.get("/api/zones", response_model=list[Zone])
async def list_zones() -> list[Zone]:
    return get_repository().list_zones()


@app.get("/api/zones/{zone_id}", response_model=Zone)
async def get_zone(zone_id: str) -> Zone:
    zone = get_repository().get_zone(zone_id)
    if zone is None:
        raise _not_found("Zone", zone_id)
    return zone


def _zone_monitoring_policy_or_restricted(zone: Zone) -> ZoneMonitoringPolicy:
    if zone.monitoring_policy is None:
        raise HTTPException(
            status_code=400,
            detail="Monitoring settings are unavailable for Privacy and Ignore Zones.",
        )
    return zone.monitoring_policy


@app.get("/api/zones/{zone_id}/monitoring-policy", response_model=ZoneMonitoringPolicy)
async def get_zone_monitoring_policy(zone_id: str) -> ZoneMonitoringPolicy:
    zone = get_repository().get_zone(zone_id)
    if zone is None:
        raise _not_found("Zone", zone_id)
    return _zone_monitoring_policy_or_restricted(zone)


@app.put("/api/zones/{zone_id}/monitoring-policy", response_model=ZoneMonitoringPolicy)
async def update_zone_monitoring_policy(
    zone_id: str,
    payload: ZoneMonitoringPolicyUpdate,
) -> ZoneMonitoringPolicy:
    repository = get_repository()
    try:
        zone = repository.update_zone_monitoring_policy(zone_id, payload)
    except ValueError as error:
        if str(error) == "restricted_zone_monitoring_policy":
            raise HTTPException(
                status_code=400,
                detail="Monitoring settings are unavailable for Privacy and Ignore Zones.",
            ) from error
        raise
    if zone is None:
        raise _not_found("Zone", zone_id)
    return _zone_monitoring_policy_or_restricted(zone)


@app.post(
    "/api/zones/{zone_id}/monitoring-policy/restore-defaults",
    response_model=ZoneMonitoringPolicy,
)
async def restore_zone_monitoring_policy_defaults(zone_id: str) -> ZoneMonitoringPolicy:
    repository = get_repository()
    try:
        zone = repository.restore_zone_monitoring_policy_defaults(zone_id)
    except ValueError as error:
        if str(error) == "restricted_zone_monitoring_policy":
            raise HTTPException(
                status_code=400,
                detail="Monitoring settings are unavailable for Privacy and Ignore Zones.",
            ) from error
        raise
    if zone is None:
        raise _not_found("Zone", zone_id)
    return _zone_monitoring_policy_or_restricted(zone)


@app.post("/api/zones", response_model=ZoneMutationResult, status_code=201)
async def create_zone(payload: ZoneCreate) -> ZoneMutationResult:
    repository = get_repository()
    stream = repository.get_stream(payload.stream_id)
    if stream is None:
        raise _not_found("Stream", payload.stream_id)
    if len(payload.polygon) < 3:
        raise _invalid_zone_polygon()

    # Zones are user-authored stream context; later detections and events should
    # respect privacy and ignore zones without making adapters the product center.
    zone = repository.create_zone(payload)
    return ZoneMutationResult(
        zone=zone,
        zones=repository.zones_for_stream(zone.stream_id),
    )


@app.patch("/api/zones/{zone_id}", response_model=ZoneMutationResult)
async def update_zone(zone_id: str, payload: ZoneUpdate) -> ZoneMutationResult:
    repository = get_repository()
    existing_zone = repository.get_zone(zone_id)
    if existing_zone is None:
        raise _not_found("Zone", zone_id)
    if payload.polygon is not None and len(payload.polygon) < 3:
        raise _invalid_zone_polygon()

    zone = repository.update_zone(zone_id, payload)
    if zone is None:
        raise _not_found("Zone", zone_id)

    return ZoneMutationResult(
        zone=zone,
        zones=repository.zones_for_stream(zone.stream_id),
    )


@app.delete("/api/zones/{zone_id}", response_model=ZoneMutationResult)
async def delete_zone(zone_id: str) -> ZoneMutationResult:
    try:
        result = get_repository().delete_zone(zone_id)
    except ValueError as error:
        if str(error) == "zone_has_review_context":
            raise HTTPException(
                status_code=409,
                detail=(
                    "This Zone is linked to existing activity or review context. "
                    "Deactivate it instead so that history stays intact."
                ),
            ) from error
        raise
    if result is None:
        raise _not_found("Zone", zone_id)
    deleted_zone, zones = result
    return ZoneMutationResult(zone=deleted_zone, zones=zones)


@app.get("/api/events", response_model=list[Event])
async def list_events() -> list[Event]:
    return get_repository().list_events()


@app.get("/api/events/{event_id}", response_model=Event)
async def get_event(event_id: str) -> Event:
    event = get_repository().get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return event


# Detail routes are review case files: detections are evidence, zones provide
# context, and review labels are dataset-grade truth for local exports.
@app.get("/api/events/{event_id}/detail", response_model=EventDetail)
async def get_event_detail(event_id: str) -> EventDetail:
    repository = get_repository()
    event = repository.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)

    stream = repository.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    visits = repository.visits_for_event(event.id)
    media_asset = next(
        (
            repository.media_asset_for_path(visit.representative_media_path)
            for visit in visits
            if visit.representative_media_path is not None
        ),
        None,
    )
    dataset_ready = repository.event_is_dataset_ready(event)
    detection_proposals = repository.detection_proposals_for_event(event.id)
    return EventDetail(
        event=event,
        stream=stream,
        primary_zone=(
            repository.get_zone(event.primary_zone_id)
            if event.primary_zone_id is not None
            else None
        ),
        visits=visits,
        motion_evidence=repository.motion_evidence_for_event(event.id),
        media_asset=media_asset,
        detection_proposals=detection_proposals,
        detection_runs=_detection_runs_for_proposals(repository, detection_proposals),
        review_labels=repository.review_labels_for_event_tree(event.id),
        dataset_ready=dataset_ready,
        review_summary=repository.review_summary_for_dataset_state(dataset_ready),
    )


@app.get("/api/events/{event_id}/visits", response_model=list[Visit])
async def list_event_visits(event_id: str) -> list[Visit]:
    repository = get_repository()
    event = repository.get_event(event_id)
    if event is None:
        raise _not_found("Event", event_id)
    return repository.visits_for_event(event_id)


@app.get("/api/visits", response_model=list[Visit])
async def list_visits() -> list[Visit]:
    return get_repository().list_visits()


@app.post("/api/activity-library/search", response_model=ActivityLibrarySearchResponse)
async def search_activity_library(
    payload: ActivityLibrarySearchRequest,
) -> ActivityLibrarySearchResponse:
    return get_repository().search_activity_library(payload)


@app.get("/api/activity-library/saved-views", response_model=list[ActivityLibrarySavedView])
async def list_activity_library_saved_views() -> list[ActivityLibrarySavedView]:
    return get_repository().list_activity_library_saved_views()


@app.post(
    "/api/activity-library/saved-views",
    response_model=ActivityLibrarySavedView,
    status_code=201,
)
async def create_activity_library_saved_view(
    payload: ActivityLibrarySavedViewCreate,
) -> ActivityLibrarySavedView:
    try:
        return get_repository().create_activity_library_saved_view(payload)
    except ValueError as error:
        if str(error) == "activity_library_saved_view_limit":
            raise HTTPException(
                status_code=409,
                detail="You can save up to 15 Activity Library views.",
            ) from error
        raise HTTPException(status_code=400, detail="Saved view name is required.") from error


@app.patch(
    "/api/activity-library/saved-views/{view_id}",
    response_model=ActivityLibrarySavedView,
)
async def update_activity_library_saved_view(
    view_id: str,
    payload: ActivityLibrarySavedViewUpdate,
) -> ActivityLibrarySavedView:
    try:
        saved_view = get_repository().update_activity_library_saved_view(view_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Saved view name is required.") from error
    if saved_view is None:
        raise _not_found("Activity Library saved view", view_id)
    return saved_view


@app.delete("/api/activity-library/saved-views/{view_id}", status_code=204)
async def delete_activity_library_saved_view(view_id: str) -> Response:
    if not get_repository().delete_activity_library_saved_view(view_id):
        raise _not_found("Activity Library saved view", view_id)
    return Response(status_code=204)


@app.post(
    "/api/activity-library/export-selection",
    response_model=ActivityLibraryExportSelectionResponse,
)
async def create_activity_library_export_selection(
    payload: ActivityLibraryExportSelectionRequest,
) -> ActivityLibraryExportSelectionResponse:
    try:
        return get_repository().create_activity_library_export_selection(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Selected Visit export could not be created.") from error


def _collection_http_error(error: ValueError, *, collection_id: str | None = None) -> HTTPException:
    code = str(error)
    if code == "missing_collection":
        return _not_found("Collection", collection_id or "")
    if code == "collection_archived":
        return HTTPException(status_code=410, detail="This Collection is archived and its active gallery is unavailable.")
    if code == "collection_stale":
        return HTTPException(status_code=409, detail="This Collection changed elsewhere. Refresh before saving.")
    if code == "collection_name_conflict":
        return HTTPException(status_code=409, detail="An active Collection already uses that name.")
    if code == "collection_limit":
        return HTTPException(status_code=409, detail="You can keep up to 100 active Collections.")
    if code == "collection_name_required":
        return HTTPException(status_code=400, detail="Collection names cannot be empty.")
    return HTTPException(status_code=400, detail="That Collection request could not be completed.")


@app.get("/api/collections", response_model=list[VisitCollectionSummary])
async def list_visit_collections() -> list[VisitCollectionSummary]:
    return get_repository().list_visit_collections()


@app.post("/api/collections", response_model=VisitCollectionSummary, status_code=201)
async def create_visit_collection(payload: VisitCollectionCreate) -> VisitCollectionSummary:
    try:
        return get_repository().create_visit_collection(payload)
    except ValueError as error:
        raise _collection_http_error(error) from error


@app.get("/api/collections/{collection_id}", response_model=VisitCollectionSummary)
async def get_visit_collection(collection_id: str) -> VisitCollectionSummary:
    collection = get_repository().get_visit_collection(collection_id)
    if collection is None:
        raise _not_found("Collection", collection_id)
    return collection


@app.patch("/api/collections/{collection_id}", response_model=VisitCollectionSummary)
async def update_visit_collection(
    collection_id: str,
    payload: VisitCollectionUpdate,
) -> VisitCollectionSummary:
    try:
        return get_repository().update_visit_collection(collection_id, payload)
    except ValueError as error:
        raise _collection_http_error(error, collection_id=collection_id) from error


@app.post("/api/collections/{collection_id}/archive", response_model=VisitCollectionSummary)
async def archive_visit_collection(
    collection_id: str,
    payload: VisitCollectionArchiveRequest,
) -> VisitCollectionSummary:
    try:
        return get_repository().archive_visit_collection(collection_id, payload)
    except ValueError as error:
        raise _collection_http_error(error, collection_id=collection_id) from error


@app.post(
    "/api/collections/{collection_id}/visits/search",
    response_model=ActivityLibrarySearchResponse,
)
async def search_visit_collection(
    collection_id: str,
    payload: ActivityLibrarySearchRequest,
) -> ActivityLibrarySearchResponse:
    try:
        return get_repository().search_visit_collection(collection_id, payload)
    except ValueError as error:
        raise _collection_http_error(error, collection_id=collection_id) from error


@app.get(
    "/api/visits/{visit_id}/collections",
    response_model=VisitCollectionsForVisitResponse,
)
async def visit_collections_for_visit(visit_id: str) -> VisitCollectionsForVisitResponse:
    try:
        return get_repository().visit_collections_for_visit(visit_id)
    except ValueError as error:
        raise _not_found("Visit", visit_id) from error


@app.post(
    "/api/collections/{collection_id}/visits/{visit_id}",
    response_model=VisitCollectionMembershipResponse,
)
async def add_visit_collection_membership(
    collection_id: str,
    visit_id: str,
    payload: VisitCollectionMembershipRequest,
) -> VisitCollectionMembershipResponse:
    try:
        return get_repository().update_visit_collection_membership(
            collection_id, visit_id, action="add", payload=payload
        )
    except ValueError as error:
        raise _collection_http_error(error, collection_id=collection_id) from error


@app.delete(
    "/api/collections/{collection_id}/visits/{visit_id}",
    response_model=VisitCollectionMembershipResponse,
)
async def remove_visit_collection_membership(
    collection_id: str,
    visit_id: str,
    payload: VisitCollectionMembershipRequest,
) -> VisitCollectionMembershipResponse:
    try:
        return get_repository().update_visit_collection_membership(
            collection_id, visit_id, action="remove", payload=payload
        )
    except ValueError as error:
        raise _collection_http_error(error, collection_id=collection_id) from error


@app.post("/api/collections/memberships/bulk", response_model=VisitCollectionBulkResponse)
async def bulk_update_visit_collection_memberships(
    payload: VisitCollectionBulkRequest,
) -> VisitCollectionBulkResponse:
    try:
        return get_repository().bulk_update_visit_collection_memberships(payload)
    except ValueError as error:
        raise _collection_http_error(error, collection_id=payload.collection_id) from error


def _tag_http_error(error: ValueError, *, tag_id: str | None = None) -> HTTPException:
    code = str(error)
    if code == "missing_tag": return _not_found("Tag", tag_id or "")
    if code == "tag_archived": return HTTPException(status_code=410, detail="This tag is archived.")
    if code == "tag_stale": return HTTPException(status_code=409, detail="This tag changed elsewhere. Refresh before saving.")
    if code == "tag_name_conflict": return HTTPException(status_code=409, detail="An active tag already uses that name.")
    if code == "tag_limit": return HTTPException(status_code=409, detail="You can keep up to 200 active tags.")
    if code in {"tag_name_required", "tag_name_unsafe"}: return HTTPException(status_code=400, detail="Use a non-empty tag name without control characters.")
    return HTTPException(status_code=400, detail="That tag request could not be completed.")


@app.get("/api/tags", response_model=list[VisitTagSummary])
async def list_visit_tags() -> list[VisitTagSummary]: return get_repository().list_visit_tags()


@app.get("/api/tags/manage", response_model=list[VisitTagSummary])
async def list_manageable_visit_tags() -> list[VisitTagSummary]:
    return get_repository().list_manageable_visit_tags()


@app.post("/api/tags", response_model=VisitTagSummary, status_code=201)
async def create_visit_tag(payload: VisitTagCreate) -> VisitTagSummary:
    try: return get_repository().create_visit_tag(payload)
    except ValueError as error: raise _tag_http_error(error) from error

@app.patch("/api/tags/{tag_id}", response_model=VisitTagSummary)
async def update_visit_tag(tag_id: str, payload: VisitTagUpdate) -> VisitTagSummary:
    try: return get_repository().update_visit_tag(tag_id, payload)
    except ValueError as error: raise _tag_http_error(error, tag_id=tag_id) from error

@app.post("/api/tags/{tag_id}/archive", response_model=VisitTagSummary)
async def archive_visit_tag(tag_id: str, payload: VisitTagArchiveRequest) -> VisitTagSummary:
    try: return get_repository().archive_visit_tag(tag_id, payload)
    except ValueError as error: raise _tag_http_error(error, tag_id=tag_id) from error

@app.get("/api/visits/{visit_id}/tags", response_model=VisitTagsForVisitResponse)
async def tags_for_visit(visit_id: str) -> VisitTagsForVisitResponse:
    try: return get_repository().tags_for_visit(visit_id)
    except ValueError as error: raise _not_found("Visit", visit_id) from error

@app.post("/api/tags/{tag_id}/visits/{visit_id}", response_model=VisitTagMembershipResponse)
async def add_visit_tag(tag_id: str, visit_id: str, payload: VisitTagMembershipRequest) -> VisitTagMembershipResponse:
    try: return get_repository().update_visit_tag_membership(tag_id, visit_id, action="add", payload=payload)
    except ValueError as error: raise _tag_http_error(error, tag_id=tag_id) from error

@app.delete("/api/tags/{tag_id}/visits/{visit_id}", response_model=VisitTagMembershipResponse)
async def remove_visit_tag(tag_id: str, visit_id: str, payload: VisitTagMembershipRequest) -> VisitTagMembershipResponse:
    try: return get_repository().update_visit_tag_membership(tag_id, visit_id, action="remove", payload=payload)
    except ValueError as error: raise _tag_http_error(error, tag_id=tag_id) from error

@app.post("/api/tags/memberships/bulk", response_model=VisitTagBulkResponse)
async def bulk_update_visit_tags(payload: VisitTagBulkRequest) -> VisitTagBulkResponse:
    try: return get_repository().bulk_update_visit_tag_memberships(payload)
    except ValueError as error: raise _tag_http_error(error, tag_id=payload.tag_id) from error


@app.get("/api/visits/{visit_id}/correction-history", response_model=VisitReviewHistory)
async def get_visit_correction_history(visit_id: str) -> VisitReviewHistory:
    history = get_repository().visit_review_history(visit_id)
    if history is None:
        raise _not_found("Visit", visit_id)
    return history


@app.get("/api/visits/{visit_id}/organization", response_model=VisitOrganizationState)
async def get_visit_organization(visit_id: str) -> VisitOrganizationState:
    try:
        return get_repository().visit_organization(visit_id)
    except ValueError as error:
        raise _not_found("Visit", visit_id) from error


@app.put("/api/visits/{visit_id}/organization", response_model=VisitOrganizationState)
async def update_visit_organization(visit_id: str, payload: VisitOrganizationUpdate) -> VisitOrganizationState:
    try:
        return get_repository().update_visit_organization(visit_id, payload)
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        if str(error) == "organization_stale":
            raise HTTPException(status_code=409, detail="This note changed elsewhere. Refresh it before saving.") from error
        raise HTTPException(status_code=400, detail="Note text contains unsupported control characters.") from error


@app.post("/api/visit-organization/bulk", response_model=VisitOrganizationBulkResponse)
async def bulk_update_visit_organization(payload: VisitOrganizationBulkRequest) -> VisitOrganizationBulkResponse:
    return get_repository().bulk_update_visit_organization(payload)


@app.get(
    "/api/visits/{visit_id}/identification-assistant",
    response_model=VisitIdentificationAssistantResponse,
)
async def get_visit_identification_assistant(
    visit_id: str,
) -> VisitIdentificationAssistantResponse:
    try:
        return get_repository().get_visit_identification_assistant(visit_id)
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(status_code=400, detail="Identification Assistant is unavailable.") from error


@app.post(
    "/api/visits/{visit_id}/identification-assistant",
    response_model=VisitIdentificationAssistantResponse,
)
def start_visit_identification_assistant(
    visit_id: str,
    payload: VisitIdentificationAssistantRequest,
) -> VisitIdentificationAssistantResponse:
    # Optional local model work remains explicitly user-triggered and bounded to
    # saved Visit evidence; it cannot create a correction or reviewed truth.
    try:
        return get_repository().start_visit_identification_assistant(visit_id, payload)
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        if str(error) == "identification_idempotency_conflict":
            raise HTTPException(
                status_code=409,
                detail="This identification request key belongs to a different Visit or evidence mode.",
            ) from error
        raise HTTPException(status_code=400, detail="Identification Assistant could not start.") from error


@app.get("/api/visits/{visit_id}", response_model=Visit)
async def get_visit(visit_id: str) -> Visit:
    visit = get_repository().get_visit(visit_id)
    if visit is None:
        raise _not_found("Visit", visit_id)
    return visit


@app.get("/api/visits/{visit_id}/detail", response_model=VisitDetail)
async def get_visit_detail(visit_id: str) -> VisitDetail:
    repository = get_repository()
    visit = repository.get_visit(visit_id)
    if visit is None:
        raise _not_found("Visit", visit_id)

    event = repository.get_event(visit.event_id)
    if event is None:
        raise _not_found("Event", visit.event_id)

    stream = repository.get_stream(event.stream_id)
    if stream is None:
        raise _not_found("Stream", event.stream_id)

    dataset_ready = repository.visit_is_dataset_ready(visit)
    detection_proposals = repository.detection_proposals_for_visit(visit.id)
    review_history = repository.visit_review_history(visit.id)
    if review_history is None:
        raise _not_found("Visit", visit_id)
    media_asset = repository.media_asset_for_path(visit.representative_media_path)
    # Multi-Subject Visit Assembly & Review v1, Phase 2: every other Visit
    # sharing this Event -- empty for the common single-subject case, since
    # `visits_for_event` then returns only this Visit itself.
    sibling_visits = [
        sibling for sibling in repository.visits_for_event(event.id) if sibling.id != visit.id
    ]
    return VisitDetail(
        visit=visit.model_copy(update={"representative_media_path": None}),
        event=event,
        stream=stream,
        primary_zone=(
            repository.get_zone(visit.zone_id or event.primary_zone_id)
            if (visit.zone_id or event.primary_zone_id) is not None
            else None
        ),
        detections=event.detections,
        motion_evidence=repository.motion_evidence_for_visit(visit.id),
        media_asset=(
            media_asset.model_copy(update={"local_path": ""})
            if media_asset is not None
            else None
        ),
        evidence_frames=repository.visit_evidence_frames(visit.id),
        effective_primary=repository.effective_primary_preview(visit.id),
        classifier_supporting_evidence=repository.classifier_supporting_evidence(visit.id),
        crop_history=repository.visit_crop_history(visit.id),
        stale_species_suggestions=repository.visit_has_stale_species_suggestions(visit.id),
        detection_proposals=detection_proposals,
        detection_runs=_detection_runs_for_proposals(repository, detection_proposals),
        review_labels=(
            repository.review_labels_for_event(event.id)
            + repository.review_labels_for_visit(visit.id)
        ),
        correction_history=review_history.entries,
        curation_history=repository.visit_curation_history(visit.id),
        resulting_visits=repository.resulting_visits_for(visit.id),
        sibling_visits=sibling_visits,
        eligible_zones=[
            zone
            for zone in repository.zones_for_stream(event.stream_id)
            if zone.is_active and zone.zone_type not in {ZoneType.privacy, ZoneType.ignore}
        ],
        review_state_token=review_history.review_state_token,
        dataset_ready=dataset_ready,
        review_summary=repository.review_summary_for_dataset_state(dataset_ready),
    )


@app.post(
    "/api/visits/{visit_id}/evidence-curation",
    response_model=VisitEvidenceCurationResponse,
)
async def curate_visit_evidence(
    visit_id: str,
    payload: VisitEvidenceCurationRequest,
) -> VisitEvidenceCurationResponse:
    try:
        return get_repository().curate_visit_evidence(visit_id, payload)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This Visit changed. Refresh it before saving evidence curation.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(status_code=400, detail="Visit evidence selection is not valid.") from error


@app.post(
    "/api/visits/{visit_id}/refined-crop",
    response_model=RefinedCropResponse,
)
async def create_refined_visit_crop(
    visit_id: str,
    payload: RefinedCropCreateRequest,
) -> RefinedCropResponse:
    try:
        return get_repository().create_refined_visit_crop(visit_id, payload)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This Visit is superseded and cannot receive a refined crop.",
        ) from error
    except ValueError as error:
        reason = str(error)
        if reason == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        messages = {
            "missing_high_resolution_parent": "This Visit has no retained full-resolution image to refine.",
            "invalid_refined_crop_geometry": "Keep the crop inside the image, above the minimum size, and below the maximum area.",
            "missing_media_file": "The retained full-resolution image is unavailable locally.",
            "invalid_high_resolution_parent": "The retained full-resolution image could not be used to create a crop.",
        }
        raise HTTPException(
            status_code=400,
            detail=messages.get(reason, "The refined crop could not be saved."),
        ) from error


@app.post(
    "/api/visits/{visit_id}/crop-history/{media_asset_id}/promote",
    response_model=RefinedCropResponse,
)
async def promote_visit_crop_history(
    visit_id: str,
    media_asset_id: str,
) -> RefinedCropResponse:
    try:
        return get_repository().promote_visit_crop_history(visit_id, media_asset_id)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This Visit is superseded and its crop history cannot be changed.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(
            status_code=400,
            detail="That crop is not valid retained history for this Visit.",
        ) from error


@app.post("/api/visits/{visit_id}/split/preview", response_model=VisitSplitPreview)
async def preview_visit_split(
    visit_id: str,
    payload: VisitSplitPreviewRequest,
) -> VisitSplitPreview:
    try:
        return get_repository().preview_visit_split(visit_id, payload)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This Visit changed. Refresh it before previewing the split.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(
            status_code=400,
            detail="Choose a boundary that leaves evidence in both resulting Visits.",
        ) from error


@app.post("/api/visits/{visit_id}/split", response_model=VisitSplitResponse)
async def split_visit(visit_id: str, payload: VisitSplitRequest) -> VisitSplitResponse:
    try:
        return get_repository().split_visit(visit_id, payload)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This Visit changed. Refresh it before splitting.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(
            status_code=400,
            detail="The Visit could not be split with this evidence boundary.",
        ) from error


@app.get(
    "/api/visits/{visit_id}/merge-candidates",
    response_model=VisitMergeCandidatesResponse,
)
async def list_visit_merge_candidates(visit_id: str) -> VisitMergeCandidatesResponse:
    try:
        return get_repository().merge_candidates_for_visit(visit_id)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This Visit is no longer available to merge.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(status_code=400, detail="Merge candidates are not available.") from error


@app.post("/api/visits/{visit_id}/merge/preview", response_model=VisitMergePreview)
async def preview_visit_merge(
    visit_id: str,
    payload: VisitMergePreviewRequest,
) -> VisitMergePreview:
    try:
        return get_repository().preview_visit_merge(visit_id, payload)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This Visit changed. Refresh it before previewing the merge.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(
            status_code=400,
            detail="These Visits are not eligible to merge.",
        ) from error


@app.post("/api/visits/{visit_id}/merge", response_model=VisitMergeResponse)
async def merge_visits(visit_id: str, payload: VisitMergeRequest) -> VisitMergeResponse:
    try:
        return get_repository().merge_visits(visit_id, payload)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="The merge preview is no longer current. Refresh it before merging.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        if str(error) == "merge_tag_limit":
            raise HTTPException(
                status_code=409,
                detail="These Visits have more than 20 combined tags. Remove or archive tags before merging.",
            ) from error
        raise HTTPException(status_code=400, detail="These Visits cannot be merged.") from error


@app.post("/api/visits/{visit_id}/zone", response_model=VisitZoneReassignmentResponse)
async def reassign_visit_zone(
    visit_id: str,
    payload: VisitZoneReassignmentRequest,
) -> VisitZoneReassignmentResponse:
    try:
        return get_repository().reassign_visit_zone(visit_id, payload)
    except VisitCurationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This Visit changed. Refresh it before moving it to another Zone.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(
            status_code=400,
            detail="Choose an active ordinary Zone on this Stream.",
        ) from error


@app.post(
    "/api/visits/{visit_id}/revision",
    response_model=VisitReviewRevisionResponse,
)
async def revise_visit_review(
    visit_id: str,
    payload: VisitReviewRevisionCreate,
) -> VisitReviewRevisionResponse:
    try:
        return get_repository().revise_visit_review(visit_id, payload)
    except ReviewRevisionConflictError as error:
        if str(error) == "review_revision_requires_authority":
            raise HTTPException(
                status_code=400,
                detail="A revision must be an authoritative Review Decision (human review or "
                "explicitly governed imported truth), not a diagnostic assessment.",
            ) from error
        raise HTTPException(
            status_code=409,
            detail="This reviewed Visit changed. Refresh it before saving a revision.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(status_code=400, detail="The reviewed Visit could not be revised.") from error


@app.post(
    "/api/visits/{visit_id}/reopen",
    response_model=VisitReviewReopenResponse,
)
async def reopen_visit_review(
    visit_id: str,
    payload: VisitReviewReopenCreate,
) -> VisitReviewReopenResponse:
    try:
        return get_repository().reopen_visit_review(visit_id, payload)
    except ReviewRevisionConflictError as error:
        if str(error) == "review_reopen_requires_authority":
            raise HTTPException(
                status_code=400,
                detail="Reopening a Visit must be an authoritative Review Decision (human review "
                "or explicitly governed imported truth), not a diagnostic assessment.",
            ) from error
        raise HTTPException(
            status_code=409,
            detail="This reviewed Visit changed. Refresh it before reopening it.",
        ) from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", visit_id) from error
        raise HTTPException(status_code=400, detail="The reviewed Visit could not be reopened.") from error


def _yard_map_http_error(error: ValueError, *, item: str = "Yard Map") -> HTTPException:
    code = str(error)
    if code == "missing_yard_map":
        return _not_found("Yard Map", "")
    if code in {"missing_yard_map_stream", "missing_yard_map_zone"}:
        return _not_found(item)
    if code == "missing_yard_map_placement":
        return _not_found("Yard Map placement", "")
    if code in {"yard_map_stale", "yard_map_placement_stale"}:
        return HTTPException(status_code=409, detail="The Yard Map changed elsewhere. Refresh before saving.")
    if code == "yard_map_exists":
        return HTTPException(status_code=409, detail="A Yard Map is already configured. Refresh it before changing setup.")
    if code == "yard_map_background_too_large":
        return HTTPException(status_code=413, detail="Choose a yard image no larger than 10 MB.")
    if code in {"yard_map_background_content_type", "yard_map_background_unsupported"}:
        return HTTPException(status_code=400, detail="Use a JPEG, PNG, or WebP image with a matching content type.")
    if code in {"yard_map_background_dimensions", "yard_map_background_empty"}:
        return HTTPException(status_code=400, detail="Choose a valid image between 32 and 8192 pixels on each side.")
    if code == "yard_map_media_root_unsafe":
        return HTTPException(status_code=400, detail="The managed local yard-image storage is unavailable safely.")
    return HTTPException(status_code=400, detail="That Yard Map change could not be completed.")


@app.get("/api/yard-map", response_model=YardMapResponse)
async def get_yard_map(
    range: str = Query(default="today", pattern="^(today|last_24_hours|last_7_days)$"),
) -> YardMapResponse:
    return get_repository().yard_map(activity_range=range)


@app.post("/api/yard-map/blank", response_model=YardMapResponse, status_code=201)
async def create_blank_yard_map(payload: YardMapBlankCreate) -> YardMapResponse:
    try:
        return get_repository().create_blank_yard_map(payload)
    except ValueError as error:
        raise _yard_map_http_error(error) from error


@app.patch("/api/yard-map", response_model=YardMapResponse)
async def update_yard_map_settings(payload: YardMapSettingsUpdate) -> YardMapResponse:
    try:
        return get_repository().update_yard_map_settings(payload)
    except ValueError as error:
        raise _yard_map_http_error(error) from error


@app.post("/api/yard-map/background", response_model=YardMapResponse)
async def replace_yard_map_background(
    file: UploadFile = File(...),
    expected_state_token: str | None = Form(default=None),
    idempotency_key: str = Form(...),
) -> YardMapResponse:
    try:
        return get_repository().replace_yard_map_background(
            content=await file.read(),
            content_type=file.content_type or "",
            expected_state_token=expected_state_token,
            idempotency_key=idempotency_key,
        )
    except ValueError as error:
        raise _yard_map_http_error(error) from error


@app.get("/api/yard-map/background")
async def get_yard_map_background():
    background = get_repository().yard_map_background_file()
    if background is None:
        raise _not_found("Yard Map background", "")
    path, content_type = background
    if "pytest" in sys.modules:
        return Response(path.read_bytes(), media_type=content_type)
    return FileResponse(path, media_type=content_type)


@app.delete("/api/yard-map/background", response_model=YardMapResponse)
async def remove_yard_map_background(payload: YardMapBackgroundDelete) -> YardMapResponse:
    try:
        return get_repository().remove_yard_map_background(payload)
    except ValueError as error:
        raise _yard_map_http_error(error) from error


@app.put("/api/yard-map/streams/{stream_id}", response_model=YardMapResponse)
async def update_yard_map_stream_placement(
    stream_id: str,
    payload: YardMapStreamPlacementUpdate,
) -> YardMapResponse:
    try:
        return get_repository().update_yard_map_stream_placement(stream_id, payload)
    except ValueError as error:
        raise _yard_map_http_error(error, item="Stream") from error


@app.delete("/api/yard-map/streams/{stream_id}", response_model=YardMapResponse)
async def remove_yard_map_stream_placement(
    stream_id: str,
    payload: YardMapPlacementDelete,
) -> YardMapResponse:
    try:
        return get_repository().remove_yard_map_stream_placement(stream_id, payload)
    except ValueError as error:
        raise _yard_map_http_error(error, item="Stream") from error


@app.put("/api/yard-map/zones/{zone_id}", response_model=YardMapResponse)
async def update_yard_map_zone_placement(
    zone_id: str,
    payload: YardMapZonePlacementUpdate,
) -> YardMapResponse:
    try:
        return get_repository().update_yard_map_zone_placement(zone_id, payload)
    except ValueError as error:
        raise _yard_map_http_error(error, item="Zone") from error


@app.delete("/api/yard-map/zones/{zone_id}", response_model=YardMapResponse)
async def remove_yard_map_zone_placement(
    zone_id: str,
    payload: YardMapPlacementDelete,
) -> YardMapResponse:
    try:
        return get_repository().remove_yard_map_zone_placement(zone_id, payload)
    except ValueError as error:
        raise _yard_map_http_error(error, item="Zone") from error


@app.get("/api/media", response_model=list[MediaAsset])
async def list_media_assets() -> list[MediaAsset]:
    return get_repository().list_media_assets()


@app.post("/api/media/import", response_model=MediaImportResult, status_code=201)
async def import_media(
    file: UploadFile = File(...),
    stream_id: str | None = Form(default=None),
    zone_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    subject_label: str = Form(default="unknown_animal"),
    species_guess: str | None = Form(default=None),
    notes: str | None = Form(default=None),
) -> MediaImportResult:
    content = await file.read()
    try:
        return get_repository().create_media_import(
            content=content,
            original_filename=file.filename or "imported-media",
            content_type=file.content_type or "",
            stream_id=stream_id or None,
            zone_id=zone_id or None,
            title=title,
            subject_label=subject_label,
            species_guess=species_guess,
            notes=notes,
        )
    except ValueError as error:
        raise _media_import_error(error) from error


@app.post("/api/media/folder-preview", response_model=FolderImportPreview)
async def preview_folder_import(
    payload: FolderImportPreviewRequest,
) -> FolderImportPreview:
    try:
        return get_repository().preview_folder_import(payload.folder_path)
    except ValueError as error:
        raise _folder_import_error(error) from error


@app.post(
    "/api/media/folder-import", response_model=FolderImportResult, status_code=201
)
async def import_folder_media(payload: FolderImportCreate) -> FolderImportResult:
    try:
        return get_repository().import_folder_media(payload)
    except ValueError as error:
        raise _folder_import_error(error) from error


@app.get(
    "/api/media/saved-preview-retention",
    response_model=SavedMediaRetentionReportResponse,
)
async def saved_preview_retention_report() -> SavedMediaRetentionReportResponse:
    return get_repository().saved_preview_retention_report()


@app.post(
    "/api/media/saved-preview-retention/dry-run-cleanup",
    response_model=SavedMediaCleanupDryRunResponse,
)
async def saved_preview_cleanup_dry_run(
    payload: SavedMediaCleanupDryRunRequest | None = None,
) -> SavedMediaCleanupDryRunResponse:
    return get_repository().saved_preview_cleanup_dry_run(
        payload or SavedMediaCleanupDryRunRequest(),
    )


@app.post(
    "/api/media/bulk-create-motion-evidence",
    response_model=SavedMediaBulkMotionEvidenceResponse,
)
async def bulk_create_motion_evidence_from_saved_media(
    payload: SavedMediaBulkMotionEvidenceRequest,
) -> SavedMediaBulkMotionEvidenceResponse:
    # Bulk media handoff creates pending evidence only.
    return get_repository().bulk_create_motion_evidence_from_saved_media(payload)


@app.post(
    "/api/folder-import/evidence/dry-run",
    response_model=FolderImportEvidenceBatchDryRunResponse,
)
async def dry_run_folder_import_evidence_batch(
    payload: FolderImportEvidenceBatchDryRunRequest | None = None,
) -> FolderImportEvidenceBatchDryRunResponse:
    # Dry-run only: no MotionEvidence, Events, Visits, labels, or truth are created.
    try:
        return get_repository().dry_run_folder_import_evidence_batch(
            payload or FolderImportEvidenceBatchDryRunRequest(),
        )
    except ValueError as error:
        raise _folder_import_evidence_dry_run_error(error) from error


@app.post(
    "/api/folder-import/evidence/batch",
    response_model=FolderImportEvidenceBatchCreateResponse,
)
async def create_folder_import_evidence_batch(
    payload: FolderImportEvidenceBatchCreateRequest | None = None,
) -> FolderImportEvidenceBatchCreateResponse:
    # Confirmed batch handoff creates pending evidence only.
    try:
        return get_repository().create_folder_import_evidence_batch(
            payload or FolderImportEvidenceBatchCreateRequest(),
        )
    except ValueError as error:
        raise _folder_import_evidence_batch_create_error(error) from error


@app.post(
    "/api/media/{media_id}/cleanup-preview", response_model=SavedMediaCleanupResponse
)
async def cleanup_saved_preview_media(
    media_id: str,
    payload: SavedMediaCleanupRequest | None = None,
) -> SavedMediaCleanupResponse:
    try:
        response = get_repository().cleanup_saved_preview_media(
            media_id,
            payload or SavedMediaCleanupRequest(),
        )
    except ValueError as error:
        raise _saved_media_cleanup_error(error, media_id) from error
    if response is None:
        raise _not_found("Media asset", media_id)
    return response


@app.get("/api/media/{media_id}", response_model=MediaAsset)
async def get_media_asset(media_id: str) -> MediaAsset:
    asset = get_repository().get_media_asset(media_id)
    if asset is None:
        raise _not_found("Media asset", media_id)
    return asset


@app.post(
    "/api/media/{media_id}/create-motion-evidence",
    response_model=SavedPreviewMotionEvidenceResponse,
    status_code=201,
)
async def create_motion_evidence_from_saved_media(
    media_id: str,
    response: Response,
    payload: SavedPreviewMotionEvidenceRequest | None = None,
) -> SavedPreviewMotionEvidenceResponse:
    # Explicit media handoff creates pending evidence only.
    try:
        result = get_repository().create_motion_evidence_from_saved_media(
            media_id,
            payload or SavedPreviewMotionEvidenceRequest(),
        )
    except ValueError as error:
        raise _saved_preview_motion_evidence_error(error, media_id) from error
    if result.duplicate_skipped:
        response.status_code = 200

    return SavedPreviewMotionEvidenceResponse(
        motion_evidence_id=result.evidence.id,
        media_asset_id=media_id,
        source_id=result.evidence.source_id,
        stream_id=result.evidence.stream_id,
        zone_id=result.evidence.zone_id,
        status=result.evidence.status,
        message=(
            "Existing MotionEvidence already references this media. "
            "No duplicate evidence was created."
            if result.duplicate_skipped
            else (
                "Created pending MotionEvidence from media. "
                "No Events, Visits, labels, or truth were created."
            )
        ),
        creates_event=False,
        creates_visit=False,
        creates_truth=False,
        duplicate_skipped=result.duplicate_skipped,
        existing_motion_evidence_id=result.existing_motion_evidence_id,
        provenance_kind=result.provenance_kind,
        warnings=result.warnings,
    )


@app.get("/api/media/{media_id}/file")
async def get_media_file(media_id: str):
    repository = get_repository()
    asset = repository.get_media_asset(media_id)
    path = repository.media_file_path(media_id)
    if asset is None or path is None:
        raise _not_found("Media asset", media_id)
    if not path.exists():
        raise _not_found("Media file", media_id)
    if "pytest" in sys.modules:
        # The local ASGI test transport hangs on FileResponse; runtime still streams.
        return Response(
            path.read_bytes(),
            media_type=asset.content_type,
            headers={
                "content-disposition": f'attachment; filename="{asset.original_filename}"'
            },
        )
    return FileResponse(
        path,
        media_type=asset.content_type,
        filename=asset.original_filename,
    )


_MEDIA_PREVIEW_MAX_SOURCE_BYTES = 16_000_000
_MEDIA_PREVIEW_MAX_DIMENSION = 1600
_MEDIA_PREVIEW_MAX_OUTPUT_BYTES = 3_000_000


@app.get("/api/media/{media_id}/preview")
async def get_media_preview(media_id: str):
    """Return a bounded display derivative without retaining another media asset."""

    repository = get_repository()
    asset = repository.get_media_asset(media_id)
    path = repository.media_file_path(media_id)
    if asset is None or path is None or not path.exists():
        raise _not_found("Media asset", media_id)
    if asset.media_type != "image" or asset.file_size_bytes > _MEDIA_PREVIEW_MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="This image is unavailable for bounded preview.")

    try:
        source = path.read_bytes()
        image = cv2.imdecode(np.frombuffer(source, dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError as error:
        raise HTTPException(status_code=404, detail="Preview image is unavailable.") from error
    if image is None or image.size == 0:
        raise HTTPException(status_code=400, detail="Preview image is invalid.")

    height, width = image.shape[:2]
    scale = min(1.0, _MEDIA_PREVIEW_MAX_DIMENSION / max(width, height))
    if scale < 1.0:
        image = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    preview: bytes | None = None
    for quality in (85, 72, 60):
        encoded, candidate = cv2.imencode(
            ".jpg",
            image,
            [cv2.IMWRITE_JPEG_QUALITY, quality],
        )
        if encoded and len(candidate) <= _MEDIA_PREVIEW_MAX_OUTPUT_BYTES:
            preview = candidate.tobytes()
            break
    if preview is None:
        raise HTTPException(status_code=413, detail="This image is unavailable for bounded preview.")
    return Response(
        preview,
        media_type="image/jpeg",
        headers={"cache-control": "private, max-age=300"},
    )


@app.get("/api/media/{media_id}/full-resolution")
async def get_media_full_resolution(media_id: str):
    """Serve an explicit original-image view; review surfaces use bounded previews."""

    repository = get_repository()
    asset = repository.get_media_asset(media_id)
    path = repository.media_file_path(media_id)
    if asset is None or path is None or not path.exists():
        raise _not_found("Media asset", media_id)
    if asset.media_type != "image":
        raise HTTPException(status_code=400, detail="This media does not have an image view.")
    if "pytest" in sys.modules:
        return Response(path.read_bytes(), media_type=asset.content_type)
    return FileResponse(path, media_type=asset.content_type)


@app.get("/api/model-adapters", response_model=list[ModelAdapter])
async def list_model_adapters() -> list[ModelAdapter]:
    return get_repository().list_model_adapters()


@app.get("/api/model-adapters/evaluation", response_model=AdapterEvaluationSummary)
async def get_model_adapter_evaluation(
    adapter_id: str | None = None,
) -> AdapterEvaluationSummary:
    try:
        return get_repository().model_adapter_evaluation_summary(adapter_id)
    except ValueError as error:
        raise _model_adapter_error(error) from error


@app.get("/api/model-readiness/summary", response_model=ModelReadinessSummary)
async def get_model_readiness_summary() -> ModelReadinessSummary:
    return get_repository().model_readiness_summary()


@app.get("/api/model-adapters/{adapter_id}", response_model=ModelAdapter)
async def get_model_adapter(adapter_id: str) -> ModelAdapter:
    adapter = get_repository().get_model_adapter(adapter_id)
    if adapter is None:
        raise _not_found("Model adapter", adapter_id)
    return adapter


@app.post("/api/model-adapters/{adapter_id}/runs", response_model=ModelAdapterRunResult)
async def run_model_adapter(
    adapter_id: str,
    payload: ModelAdapterRunRequest,
) -> ModelAdapterRunResult:
    repository = get_repository()
    if repository.get_model_adapter(adapter_id) is None:
        raise _not_found("Model adapter", adapter_id)

    try:
        return repository.run_model_adapter(adapter_id, payload)
    except ValueError as error:
        raise _model_adapter_error(error) from error


@app.get("/api/detection-runs", response_model=list[DetectionRun])
async def list_detection_runs() -> list[DetectionRun]:
    return get_repository().list_detection_runs()


@app.post("/api/detection-runs", response_model=DetectionRun, status_code=201)
async def create_detection_run(payload: DetectionRunCreate) -> DetectionRun:
    try:
        return get_repository().create_detection_run(payload)
    except ValueError as error:
        raise _detection_interface_error(error) from error


@app.post(
    "/api/detection-runs/demo", response_model=DemoDetectionRunResult, status_code=201
)
async def create_demo_detection_run(
    payload: DemoDetectionRunCreate,
) -> DemoDetectionRunResult:
    try:
        return get_repository().create_demo_detection_run(payload)
    except ValueError as error:
        raise _detection_interface_error(error) from error


@app.get("/api/detection-runs/{run_id}", response_model=DetectionRun)
async def get_detection_run(run_id: str) -> DetectionRun:
    run = get_repository().get_detection_run(run_id)
    if run is None:
        raise _not_found("Detection run", run_id)
    return run


@app.get(
    "/api/detection-runs/{run_id}/proposals", response_model=list[DetectionProposal]
)
async def list_detection_run_proposals(run_id: str) -> list[DetectionProposal]:
    proposals = get_repository().detection_proposals_for_run(run_id)
    if proposals is None:
        raise _not_found("Detection run", run_id)
    return proposals


@app.get("/api/detection-proposals", response_model=list[DetectionProposal])
async def list_detection_proposals() -> list[DetectionProposal]:
    return get_repository().list_detection_proposals()


@app.post("/api/detection-proposals", response_model=DetectionProposal, status_code=201)
async def create_detection_proposal(
    payload: DetectionProposalCreate,
) -> DetectionProposal:
    try:
        return get_repository().create_detection_proposal(payload)
    except ValueError as error:
        raise _detection_interface_error(error) from error


@app.get("/api/detection-proposals/{proposal_id}", response_model=DetectionProposal)
async def get_detection_proposal(proposal_id: str) -> DetectionProposal:
    proposal = get_repository().get_detection_proposal(proposal_id)
    if proposal is None:
        raise _not_found("Detection proposal", proposal_id)
    return proposal


@app.post(
    "/api/detection-proposals/{proposal_id}/decision",
    response_model=DetectionProposalDecisionResult,
)
async def decide_detection_proposal(
    proposal_id: str,
    payload: DetectionProposalDecisionCreate,
) -> DetectionProposalDecisionResult:
    try:
        result = get_repository().decide_detection_proposal(proposal_id, payload)
    except ValueError as error:
        raise _detection_interface_error(error) from error

    if result is None:
        raise _not_found("Detection proposal", proposal_id)
    return result


@app.get("/api/review-queue", response_model=list[ReviewQueueItem])
async def list_review_queue(
    include_reviewed: bool = Query(default=False),
) -> list[ReviewQueueItem]:
    """Read compact review work; reviewed history is opt-in for Product Mode."""

    return get_repository().review_queue_items(include_reviewed=include_reviewed)


@app.post(
    "/api/review-queue/fast/navigate",
    response_model=FastReviewQueueNavigationResponse,
)
async def navigate_fast_review_queue(
    payload: FastReviewQueueNavigationRequest,
) -> FastReviewQueueNavigationResponse:
    return get_repository().navigate_fast_review_queue(payload)


@app.post(
    "/api/review-queue/fast/correct",
    response_model=FastReviewCorrectionResponse,
)
async def create_fast_review_correction(
    payload: FastReviewCorrectionCreate,
) -> FastReviewCorrectionResponse:
    try:
        return get_repository().create_fast_review_correction(payload)
    except FastReviewConflictError as error:
        # A queued Visit can be corrected in another tab; never append a second truth row.
        raise HTTPException(status_code=409, detail="Fast Review item is stale or already resolved.") from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", payload.target_id) from error
        if str(error) == "fast_review_visits_only":
            raise HTTPException(status_code=400, detail="Fast Review is available for Visits only.") from error
        raise HTTPException(status_code=400, detail="Fast Review correction could not be saved.") from error


@app.post(
    "/api/review-queue/fast/undo",
    response_model=FastReviewUndoResponse,
)
async def undo_fast_review_correction(
    payload: FastReviewUndoRequest,
) -> FastReviewUndoResponse:
    try:
        return get_repository().undo_fast_review_correction(payload)
    except FastReviewConflictError as error:
        # Undo is deliberately limited to the caller's latest un-replaced correction.
        raise HTTPException(status_code=409, detail="Fast Review undo is no longer available.") from error
    except ValueError as error:
        if str(error) == "missing_visit":
            raise _not_found("Visit", payload.review_label_id) from error
        raise HTTPException(status_code=400, detail="Fast Review undo could not be completed.") from error


@app.post(
    "/api/review-queue/species-suggestions/prepare",
    response_model=ReviewQueueSpeciesSuggestionBatchPrepareResponse,
)
async def prepare_review_queue_species_suggestions(
    payload: ReviewQueueSpeciesSuggestionBatchPrepareRequest,
) -> ReviewQueueSpeciesSuggestionBatchPrepareResponse:
    # Preflight is deliberately bounded and read-only. The browser invokes the
    # established single-Visit operation one at a time after this response.
    return get_repository().prepare_review_queue_species_suggestions(payload)


@app.post(
    "/api/review-queue/{target_type}/{target_id}/identify",
    response_model=ReviewIdentificationResponse,
)
def identify_review_queue_item(
    target_type: str,
    target_id: str,
    payload: ReviewIdentificationRequest | None = None,
) -> ReviewIdentificationResponse:
    # Optional local classifiers are request-bound but CPU-heavy. A synchronous
    # route lets FastAPI isolate this work from the main async event loop.
    if target_type not in {"event", "visit"}:
        raise _unsupported_target(target_type)

    try:
        return get_repository().identify_review_queue_item(
            target_type,
            target_id,
            payload or ReviewIdentificationRequest(),
        )
    except ValueError as error:
        raise _review_identification_error(error) from error


@app.post(
    "/api/review-queue/bulk-correct",
    response_model=ReviewQueueBulkCorrectionResponse,
)
async def bulk_correct_review_queue_items(
    payload: ReviewQueueBulkCorrectionRequest,
) -> ReviewQueueBulkCorrectionResponse:
    try:
        return get_repository().bulk_correct_review_queue_items(payload)
    except ValueError as error:
        if str(error) == "missing_review_label":
            raise HTTPException(
                status_code=400, detail="A correction label is required."
            ) from error
        raise HTTPException(
            status_code=400, detail="Review Queue bulk correction failed."
        ) from error


@app.get("/api/review-labels", response_model=list[ReviewLabel])
async def list_review_labels() -> list[ReviewLabel]:
    return get_repository().list_review_labels()


@app.post("/api/review-labels", response_model=ReviewCorrectionResult, status_code=201)
async def create_review_label(
    payload: ReviewCorrectionCreate,
) -> ReviewCorrectionResult:
    repository = get_repository()

    if payload.target_type == "visit":
        if repository.get_visit(payload.target_id) is None:
            raise _not_found("Visit", payload.target_id)

        # Review labels are user-confirmed dataset truth; detections remain evidence.
        return repository.create_review_label(payload)

    if payload.target_type == "event":
        if repository.get_event(payload.target_id) is None:
            raise _not_found("Event", payload.target_id)

        return repository.create_review_label(payload)

    raise _unsupported_target(payload.target_type)


@app.post(
    "/api/review-labels/{review_label_id}/reclassify-provenance",
    response_model=ReviewLabel,
)
async def reclassify_review_label_provenance(
    review_label_id: str,
    payload: ReviewLabelProvenanceReclassifyRequest,
) -> ReviewLabel:
    """Bounded maintenance endpoint (see
    docs/review-decision-provenance-contract.md Part 8 and
    scripts/repair_review_label_provenance.py). Not part of the normal
    interactive review flow and not called by the frontend -- it exists so
    a bounded, auditable maintenance script can durably repair a specific,
    already-identified ReviewLabel's provenance (for example a row created
    through this exact gap before it was closed) without direct database
    surgery."""

    try:
        return get_repository().reclassify_review_label_provenance(
            review_label_id,
            review_origin=payload.review_origin,
            reviewer_identity=payload.reviewer_identity,
            expected_current_review_origin=payload.expected_current_review_origin,
        )
    except ReviewProvenanceConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="This ReviewLabel's provenance already changed since it was last inspected.",
        ) from error
    except ReviewProvenanceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ValueError as error:
        if str(error) == "missing_review_label":
            raise _not_found("Review label", review_label_id) from error
        raise HTTPException(
            status_code=400, detail="The ReviewLabel provenance could not be reclassified."
        ) from error


@app.get("/api/dataset-exports", response_model=list[DatasetExport])
async def list_dataset_exports() -> list[DatasetExport]:
    return get_repository().list_dataset_exports()


@app.post("/api/dataset-exports", response_model=DatasetExportDetail, status_code=201)
async def create_dataset_export(payload: DatasetExportCreate) -> DatasetExportDetail:
    repository = get_repository()
    dataset_export = repository.create_dataset_export(payload)
    manifest = repository.build_dataset_manifest(dataset_export.id)
    if manifest is None:
        raise _not_found("Dataset export", dataset_export.id)
    return DatasetExportDetail(export=dataset_export, manifest=manifest)


@app.get("/api/dataset-exports/{export_id}", response_model=DatasetExportDetail)
async def get_dataset_export(export_id: str) -> DatasetExportDetail:
    repository = get_repository()
    dataset_export = repository.get_dataset_export(export_id)
    if dataset_export is None:
        raise _not_found("Dataset export", export_id)

    manifest = repository.build_dataset_manifest(export_id)
    if manifest is None:
        raise _not_found("Dataset export", export_id)

    return DatasetExportDetail(export=dataset_export, manifest=manifest)


@app.get(
    "/api/dataset-exports/{export_id}/manifest", response_model=DatasetExportManifest
)
async def get_dataset_export_manifest(export_id: str) -> DatasetExportManifest:
    manifest = get_repository().build_dataset_manifest(export_id)
    if manifest is None:
        raise _not_found("Dataset export", export_id)
    return manifest


@app.get("/api/dataset-coverage/summary", response_model=DatasetCoverageSummary)
async def get_dataset_coverage_summary() -> DatasetCoverageSummary:
    return get_repository().dataset_coverage_summary()


@app.get("/api/dataset-quality/summary", response_model=DatasetQualitySummary)
async def get_dataset_quality_summary() -> DatasetQualitySummary:
    return get_repository().dataset_quality_summary()


@app.get("/api/classifier-readiness", response_model=ClassifierReadinessReport)
async def get_classifier_readiness() -> ClassifierReadinessReport:
    return get_repository().classifier_readiness_report()


@app.get(
    "/api/classifier-training-manifest",
    response_model=ClassifierTrainingManifestResponse,
)
async def get_classifier_training_manifest() -> ClassifierTrainingManifestResponse:
    return get_repository().build_classifier_training_manifest()


@app.post(
    "/api/classifier-training-manifest/exports",
    response_model=ClassifierManifestFileExportResponse,
    status_code=201,
)
async def create_classifier_training_manifest_export(
    payload: ClassifierManifestFileExportRequest,
) -> ClassifierManifestFileExportResponse:
    try:
        return get_repository().create_classifier_manifest_export(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary() -> AnalyticsSummary:
    return get_repository().analytics_summary()


@app.post("/api/analytics/zone-insights", response_model=ZoneInsightsSummary)
async def get_zone_insights(
    payload: ZoneInsightsRequest,
) -> ZoneInsightsSummary:
    """Return bounded read-only feeder and Zone comparisons from reviewed truth."""

    return get_repository().zone_insights(payload)


@app.post("/api/analytics/wildlife-insights", response_model=WildlifeInsightsSummary)
async def get_wildlife_insights(
    payload: WildlifeInsightsRequest,
) -> WildlifeInsightsSummary:
    """Return bounded current reviewed-truth insights for the Analytics page."""

    return get_repository().wildlife_insights(payload)


@app.post(
    "/api/analytics/place-activity-report",
    response_model=PlaceActivityReportResponse,
)
async def get_place_activity_report(
    payload: PlaceActivityReportRequest,
) -> PlaceActivityReportResponse:
    """Return one deterministic, read-only Place activity report for an
    explicit reporting period (see docs/place-activity-report-contract.md).
    Reuses canonical reviewed-truth resolution and durable monitoring
    exposure history; creates no review/Observation/product state."""

    return get_repository().place_activity_report(payload)


@app.get("/api/alerts/unread", response_model=ProductAlertUnreadResponse)
async def get_alert_unread() -> ProductAlertUnreadResponse:
    return get_repository().product_alert_unread()


@app.get("/api/alerts", response_model=ProductAlertListResponse)
async def list_alerts(
    category: AlertCategory | None = None,
    page_size: int = Query(default=30, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=10_000),
) -> ProductAlertListResponse:
    return get_repository().list_product_alerts(
        category=category, page_size=page_size, offset=offset,
    )


@app.post("/api/alerts/{alert_id}/read", response_model=ProductAlertUnreadResponse)
async def mark_alert_read(alert_id: str) -> ProductAlertUnreadResponse:
    if not get_repository().mark_product_alert_read(alert_id):
        raise _not_found("Alert", alert_id)
    return get_repository().product_alert_unread()


@app.post("/api/alerts/read-visible", response_model=ProductAlertUnreadResponse)
async def mark_visible_alerts_read(
    payload: ProductAlertMarkVisibleReadRequest,
) -> ProductAlertUnreadResponse:
    get_repository().mark_product_alerts_read(payload.alert_ids)
    return get_repository().product_alert_unread()


@app.post("/api/alerts/{alert_id}/dismiss", response_model=ProductAlertUnreadResponse)
async def dismiss_alert(alert_id: str) -> ProductAlertUnreadResponse:
    if not get_repository().dismiss_product_alert(alert_id):
        raise _not_found("Alert", alert_id)
    return get_repository().product_alert_unread()


@app.get("/api/bird-log/journal", response_model=WildlifeJournalOverviewResponse)
async def get_wildlife_journal(
    order: WildlifeJournalOrder = WildlifeJournalOrder.most_recent,
) -> WildlifeJournalOverviewResponse:
    """Read bounded current reviewed-wildlife label summaries for Bird Log."""

    return get_repository().wildlife_journal_overview(WildlifeJournalOverviewRequest(order=order))


@app.get("/api/bird-log/likely", response_model=LikelySpeciesOverviewResponse)
async def get_likely_species_overview() -> LikelySpeciesOverviewResponse:
    """Read bounded, currently-unreviewed automatic species suggestions for
    Bird Log's provisional section. Never reviewed truth; see
    `list_likely_species_overview`."""

    return get_repository().list_likely_species_overview()


@app.get(
    "/api/bird-log/journal/{label}",
    response_model=WildlifeJournalHistoryResponse,
)
async def get_wildlife_journal_history(
    label: str,
    preset: WildlifeJournalRangePreset = WildlifeJournalRangePreset.all_time,
    start_date: date | None = None,
    end_date: date | None = None,
    stream_id: str | None = None,
    zone_id: str | None = None,
    favorites_only: bool = False,
    tag_id: str | None = None,
    gallery_order: WildlifeJournalGalleryOrder = WildlifeJournalGalleryOrder.newest,
    page_size: int = Query(default=24, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=10_000),
) -> WildlifeJournalHistoryResponse:
    if len(label) > 256:
        raise _not_found("Wildlife Journal label", label)
    if preset == WildlifeJournalRangePreset.custom and (
        start_date is None
        or end_date is None
        or end_date < start_date
        or (end_date - start_date).days > 365
    ):
        raise HTTPException(status_code=422, detail="Choose a valid custom date range up to 366 days.")
    response = get_repository().wildlife_journal_history(
        label,
        WildlifeJournalHistoryRequest(
            preset=preset,
            start_date=start_date,
            end_date=end_date,
            stream_id=stream_id,
            zone_id=zone_id,
            favorites_only=favorites_only,
            tag_id=tag_id,
            gallery_order=gallery_order,
            page_size=page_size,
            offset=offset,
        ),
    )
    if response is None:
        raise _not_found("Wildlife Journal label", label)
    return response


@app.get("/api/settings/local-data", response_model=LocalDataStatus)
async def get_local_data_status() -> LocalDataStatus:
    return get_repository().local_data_status()


@app.get("/api/setup/state", response_model=SetupState)
async def get_setup_state() -> SetupState:
    """Read-only: never inferred from Source/Stream counts, see AppSetupStateModel."""

    return get_repository().get_setup_state()


@app.put("/api/setup/state", response_model=SetupState)
async def update_setup_state(payload: SetupStateUpdate) -> SetupState:
    """Persist explicit first-run wizard progress. Creates no Source/Stream/Zone."""

    return get_repository().update_setup_state(payload)


def _storage_retention_http_error(error: ValueError) -> HTTPException:
    messages = {
        "storage_cleanup_requires_confirmation": "Confirm cleanup before moving any managed media to recovery.",
        "storage_cleanup_preview_missing": "That cleanup preview is no longer available. Generate a new preview.",
        "storage_cleanup_preview_expired": "That cleanup preview expired. Generate a new preview.",
        "storage_cleanup_preview_stale": "Managed storage or the retention policy changed. Generate a new preview.",
        "storage_cleanup_idempotency_conflict": "This request key belongs to a different cleanup preview.",
        "storage_cleanup_restore_unavailable": "That cleanup batch is not available for recovery.",
        "storage_cleanup_purge_requires_confirmation": "Confirm permanent purge after the recovery window has ended.",
        "storage_cleanup_purge_unavailable": "That cleanup batch is not available for permanent purge.",
        "storage_cleanup_recovery_active": "Recovery is still available, so permanent purge is not allowed yet.",
    }
    conflicts = {
        "storage_cleanup_busy",
        "storage_cleanup_preview_stale",
        "storage_cleanup_idempotency_conflict",
        "storage_cleanup_recovery_active",
    }
    return HTTPException(
        status_code=409 if str(error) in conflicts else 400,
        detail=messages.get(str(error), "The local storage operation could not be completed safely."),
    )


def _acquire_storage_maintenance_window() -> None:
    if not _backup_operation_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="A local backup, restore, or storage cleanup is already running.",
        )


@app.get("/api/settings/storage-retention/summary", response_model=StorageSummary)
def get_storage_retention_summary() -> StorageSummary:
    return get_repository().storage_summary()


@app.get("/api/settings/storage-retention", response_model=StorageRetentionSettings)
def get_storage_retention_settings() -> StorageRetentionSettings:
    return get_repository().storage_retention_settings()


@app.put("/api/settings/storage-retention", response_model=StorageRetentionSettings)
def update_storage_retention_settings(
    payload: StorageRetentionSettingsUpdate,
) -> StorageRetentionSettings:
    _acquire_storage_maintenance_window()
    try:
        settings, _idempotent = get_repository().update_storage_retention_settings(payload)
        _sync_local_storage_retention_service(
            enabled=settings.automatic_cleanup_enabled,
        )
        return settings
    finally:
        _backup_operation_lock.release()


@app.post(
    "/api/settings/storage-retention/cleanup-preview",
    response_model=StorageCleanupPreviewResponse,
)
def preview_storage_retention_cleanup() -> StorageCleanupPreviewResponse:
    _acquire_storage_maintenance_window()
    try:
        return get_repository().preview_storage_cleanup()
    finally:
        _backup_operation_lock.release()


@app.post(
    "/api/settings/storage-retention/cleanup",
    response_model=StorageCleanupResult,
)
def execute_storage_retention_cleanup(
    payload: StorageCleanupExecuteRequest,
) -> StorageCleanupResult:
    _acquire_storage_maintenance_window()
    try:
        return get_repository().execute_storage_cleanup(payload)
    except ValueError as error:
        raise _storage_retention_http_error(error) from error
    finally:
        _backup_operation_lock.release()


@app.get(
    "/api/settings/storage-retention/cleanup-history",
    response_model=StorageCleanupHistoryResponse,
)
def get_storage_retention_cleanup_history(
    limit: int = Query(default=20, ge=1, le=30),
) -> StorageCleanupHistoryResponse:
    return get_repository().storage_cleanup_history(limit=limit)


@app.post(
    "/api/settings/storage-retention/cleanup-history/{batch_id}/restore",
    response_model=StorageCleanupResult,
)
def restore_storage_retention_cleanup(
    batch_id: str,
    payload: StorageCleanupRestoreRequest,
) -> StorageCleanupResult:
    _acquire_storage_maintenance_window()
    try:
        result = get_repository().restore_storage_cleanup_batch(batch_id, payload)
        if result is None:
            raise _not_found("Storage cleanup batch", batch_id)
        return result
    except ValueError as error:
        raise _storage_retention_http_error(error) from error
    finally:
        _backup_operation_lock.release()


@app.post(
    "/api/settings/storage-retention/cleanup-history/{batch_id}/purge",
    response_model=StorageCleanupResult,
)
def purge_storage_retention_cleanup(
    batch_id: str,
    payload: StorageCleanupPurgeRequest,
) -> StorageCleanupResult:
    _acquire_storage_maintenance_window()
    try:
        result = get_repository().purge_storage_cleanup_batch(batch_id, payload)
        if result is None:
            raise _not_found("Storage cleanup batch", batch_id)
        return result
    except ValueError as error:
        raise _storage_retention_http_error(error) from error
    finally:
        _backup_operation_lock.release()


@app.get("/api/settings/backups", response_model=LocalBackupLibraryResponse)
def list_local_backups() -> LocalBackupLibraryResponse:
    try:
        library = _local_backup_manager().list_backups()
    except LocalBackupError as error:
        raise _local_backup_http_error(error) from error
    return LocalBackupLibraryResponse(
        backups=[_local_backup_summary(item) for item in library.backups],
        unreadable_backup_count=library.unreadable_backup_count,
        local_first_note=(
            "Backups remain local until you download or copy an artifact elsewhere. "
            "Listing does not change product data."
        ),
    )


@app.post(
    "/api/settings/backups",
    response_model=LocalBackupVerificationResponse,
    status_code=201,
)
def create_local_backup() -> LocalBackupVerificationResponse:
    if not _backup_operation_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409, detail="Another backup or restore is already running."
        )
    try:
        verification = _local_backup_manager().create_backup()
        return _local_backup_verification_response(
            verification,
            message="Backup created and verified. Product data was not changed.",
        )
    except LocalBackupError as error:
        raise _local_backup_http_error(error) from error
    finally:
        _backup_operation_lock.release()


@app.post(
    "/api/settings/backups/import",
    response_model=LocalBackupVerificationResponse,
    status_code=201,
)
def import_local_backup(
    file: UploadFile = File(...),
) -> LocalBackupVerificationResponse:
    if not _backup_operation_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409, detail="Another backup or restore is already running."
        )
    try:
        file.file.seek(0)
        verification = _local_backup_manager().import_backup(file.file)
        return _local_backup_verification_response(
            verification,
            message="Backup imported and verified. Product data was not changed.",
        )
    except LocalBackupError as error:
        raise _local_backup_http_error(error) from error
    finally:
        _backup_operation_lock.release()


@app.post(
    "/api/settings/backups/{backup_id}/verify",
    response_model=LocalBackupVerificationResponse,
)
def verify_local_backup(backup_id: str) -> LocalBackupVerificationResponse:
    try:
        verification = _local_backup_manager().verify_backup(backup_id)
        return _local_backup_verification_response(
            verification,
            message="Backup verification passed. Product data was not changed.",
        )
    except LocalBackupError as error:
        raise _local_backup_http_error(error) from error


@app.get("/api/settings/backups/{backup_id}/download")
def download_local_backup(backup_id: str) -> FileResponse:
    try:
        manager = _local_backup_manager()
        verification = manager.verify_backup(backup_id)
        path = verification.backup.archive_path
    except LocalBackupError as error:
        raise _local_backup_http_error(error) from error
    date_label = verification.backup.created_at.strftime("%Y-%m-%d")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"MockingBird-{date_label}-{backup_id[:8]}{path.suffix}",
    )


@app.post(
    "/api/settings/backups/{backup_id}/restore-plan",
    response_model=LocalBackupRestorePlan,
)
def plan_local_backup_restore(
    backup_id: str,
    payload: LocalBackupRestorePlanRequest,
) -> LocalBackupRestorePlan:
    if not _backup_operation_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409, detail="Another backup or restore is already running."
        )
    try:
        manager = _local_backup_manager()
        verification = manager.verify_backup(backup_id)
        plan = manager.create_restore_plan(
            verification,
            rebind_managed_storage=payload.rebind_managed_storage,
        )
        return _local_backup_restore_plan(plan)
    except LocalBackupError as error:
        raise _local_backup_http_error(error) from error
    finally:
        _backup_operation_lock.release()


@app.post(
    "/api/settings/backups/{backup_id}/restore",
    response_model=LocalBackupRestoreResponse,
)
def restore_local_backup(
    backup_id: str,
    payload: LocalBackupRestoreRequest,
) -> LocalBackupRestoreResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=400, detail="Confirm restore before replacing local data."
        )
    if not _backup_operation_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409, detail="Another backup or restore is already running."
        )

    transaction = None
    restored_repository: ProductRepository | None = None
    restored_repository_configured = False
    repository_closed = False
    repository_access_acquired = False
    try:
        repository = get_repository()
        manager = _local_backup_manager(repository)
        selected = manager.verify_backup(backup_id)
        restore_plan = manager.create_restore_plan(
            selected,
            rebind_managed_storage=payload.rebind_managed_storage,
        )
        if not restore_plan.restore_allowed:
            raise LocalBackupValidationError("restore_plan_not_allowed")

        db_url = repository.db_url
        media_root = repository.media_root
        classifier_export_root = repository.classifier_manifest_export_root

        # Runtime readers stop before the safety snapshot. No camera process can
        # keep writing managed media while the live database/media pair is swapped.
        _stop_runtime_activity(reason="local_backup_restore")
        safety = manager.create_backup(kind="pre_restore")
        _repository_access_lock.acquire()
        repository_access_acquired = True
        configure_repository(None)
        repository_closed = True

        transaction = manager.replace_live_files(
            selected,
            rebind_managed_storage=payload.rebind_managed_storage,
            plan=restore_plan,
        )
        restored_repository = _open_product_repository(
            db_url=db_url,
            media_root=media_root,
            classifier_manifest_export_root=classifier_export_root,
        )
        restored_repository.prepare_for_supervision("local-backup-restore")
        # Restored durable policy (armed/paused/off) is kept exactly as
        # backed up -- it is the restored truth. The runtime hold applied
        # here is the separate safety measure: it prevents an armed Stream
        # from silently resuming monitoring, including after the next
        # application restart, until the user explicitly resumes it. See
        # docs/local-backup-recovery-design.md and `apply_restore_hold`.
        restored_repository.apply_restore_hold()
        configure_repository(restored_repository)
        restored_repository_configured = True
        restored_status = restored_repository.local_data_status()
        transaction.commit()

        return LocalBackupRestoreResponse(
            restored_backup=_local_backup_summary(selected.backup),
            safety_backup=_local_backup_summary(safety.backup),
            restore_plan=_local_backup_restore_plan(
                restore_plan,
                dry_run=False,
                confirmed=True,
            ),
            status=restored_status,
            message=(
                "Backup restored with managed storage rebound and reopened. "
                if payload.rebind_managed_storage
                else "Backup restored and reopened. "
            )
            + (
                "A verified pre-restore safety backup was kept in the local backup library."
            ),
        )
    except LocalBackupError as error:
        if repository_closed:
            if restored_repository_configured:
                configure_repository(None)
            elif restored_repository is not None:
                restored_repository.close()
            if transaction is not None and not transaction.completed:
                transaction.rollback()
            try:
                recovered_repository = _open_product_repository(
                    db_url=db_url,
                    media_root=media_root,
                    classifier_manifest_export_root=classifier_export_root,
                )
                configure_repository(recovered_repository)
            except Exception as recovery_error:
                raise _local_backup_http_error(
                    LocalBackupRestoreError("restore_and_recovery_failed")
                ) from recovery_error
        raise _local_backup_http_error(error) from error
    except Exception as error:
        if repository_closed:
            if restored_repository_configured:
                configure_repository(None)
            elif restored_repository is not None:
                restored_repository.close()
            if transaction is not None and not transaction.completed:
                transaction.rollback()
            try:
                recovered_repository = _open_product_repository(
                    db_url=db_url,
                    media_root=media_root,
                    classifier_manifest_export_root=classifier_export_root,
                )
                configure_repository(recovered_repository)
            except Exception as recovery_error:
                raise _local_backup_http_error(
                    LocalBackupRestoreError("restore_and_recovery_failed")
                ) from recovery_error
        raise _local_backup_http_error(
            LocalBackupRestoreError("restore_failed")
        ) from error
    finally:
        if repository_access_acquired:
            _repository_access_lock.release()
        _backup_operation_lock.release()


@app.post("/api/settings/reset-demo-data", response_model=LocalDataStatus)
async def reset_demo_data() -> LocalDataStatus:
    # Reset restores the sample walkthrough only; real product data and media stay intact.
    return get_repository().reset_demo_data()


@app.post(
    "/api/settings/remove-sample-data",
    response_model=SampleDataRemovalResponse,
)
async def remove_sample_data(
    payload: SampleDataRemovalRequest,
) -> SampleDataRemovalResponse:
    try:
        return get_repository().remove_sample_data(confirm=payload.confirm)
    except ValueError as error:
        if str(error) == "sample_data_confirmation_required":
            raise HTTPException(
                status_code=400,
                detail="Confirm removal of the sample walkthrough.",
            ) from error
        if str(error) == "sample_data_requires_real_source":
            raise HTTPException(
                status_code=409,
                detail="Add a real camera before removing the sample walkthrough.",
            ) from error
        if str(error) == "sample_data_has_user_content":
            raise HTTPException(
                status_code=409,
                detail=(
                    "The sample camera contains added captures, evidence, Zones, or review work. "
                    "It was preserved to avoid deleting user data."
                ),
            ) from error
        raise


# Production-mode web routes come last so API, health, and documentation routes
# always win. Direct browser loads can therefore restore product/detail URLs.
@app.get("/", include_in_schema=False)
async def get_web_app_root() -> Response:
    return frontend_response("")


@app.get("/{full_path:path}", include_in_schema=False)
async def get_web_app_route(full_path: str) -> Response:
    return frontend_response(full_path)
