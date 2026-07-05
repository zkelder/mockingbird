"""FastAPI app for the MockingBird product API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import sys

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, Response, StreamingResponse

from mockingbird.api.schemas import (
    AnalyticsSummary,
    AdapterEvaluationSummary,
    CameraSource,
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
    MotionZoneInput,
    ReviewLabel,
    ReviewCorrectionCreate,
    ReviewCorrectionResult,
    ReviewQueueBulkCorrectionRequest,
    ReviewQueueBulkCorrectionResponse,
    ReviewQueueItem,
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
    SpeciesSuggestionCreateRequest,
    SpeciesSuggestionListResponse,
    SpeciesSuggestionResponse,
    SpeciesSuggestionStatus,
    SpeciesSuggestionStatusUpdateRequest,
    SourceConnectionStatus,
    SourceConnectionStatusResponse,
    SourceFolderImportRequest,
    SourceFolderImportResponse,
    SourceMonitorStartRequest,
    SourceMonitorStatusResponse,
    SourceFolderImportPreviewRequest,
    SourceFolderImportPreviewResponse,
    SourceProviderConfiguration,
    SourceProviderConfigurationUpdate,
    SourceProviderDefinition,
    SourceSetupReviewResponse,
    Stream,
    StreamPlaybackStatus,
    StreamPlaybackStatusResponse,
    TaxonomyLabel,
    Visit,
    VisitDetail,
    WebhookMotionEvidenceRequest,
    WebhookMotionEvidenceResponse,
    WebhookPayloadValidationRequest,
    WebhookPayloadValidationResponse,
    WorkerStatusResponse,
    Zone,
    ZoneCreate,
    ZoneMutationResult,
    ZoneUpdate,
)
from mockingbird.motion import (
    MotionCandidate,
    MotionFrameScore,
    MotionScore,
    MotionZone,
    extract_motion_candidates,
    score_frame_motion,
)
from mockingbird.motion.activity_crop import ActivityCropPlan, plan_activity_crop
from mockingbird.motion.activity_session import (
    ExistingActivityReference,
    recommend_activity_session,
)
from mockingbird.monitoring import (
    MonitorMotionResult,
    MonitorSnapshotResult,
    SourceMonitorManager,
    SourceMonitorOptions,
    SourceMonitorState,
)
from mockingbird.playback import local_camera_bridge, rtsp_bridge
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.sampler import (
    SamplerConfig,
    SamplerContext,
    SamplerZone,
    create_motion_evidence_from_sampler_result,
    evaluate_sampled_frame_sequence,
)
from mockingbird.sampler.saved_media_frames import (
    SavedMediaFrame,
    SavedMediaFrameDecodeError,
    load_saved_image_frame_plane,
)
from mockingbird.source_providers import external_url_preview

app = FastAPI(
    title="MockingBird API",
    version="0.1.0",
    description=(
        "Local-first outdoor video intelligence centered on streams, zones, "
        "events, visits, review, corrections, exports, and analytics."
    ),
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
_source_monitor_manager: SourceMonitorManager | None = None


def get_repository() -> ProductRepository:
    global _repository
    if _repository is None:
        _repository = ProductRepository()
    return _repository


def configure_repository(repository: ProductRepository | None) -> None:
    global _repository, _source_monitor_manager
    if _source_monitor_manager is not None:
        _source_monitor_manager.cancel_all()
        _source_monitor_manager = None
    _repository = repository


def get_source_monitor_manager() -> SourceMonitorManager:
    global _source_monitor_manager
    if _source_monitor_manager is None:
        _source_monitor_manager = SourceMonitorManager(
            capture_snapshot=_monitor_capture_snapshot,
            list_saved_images=_monitor_saved_image_ids,
            evaluate_saved_media=_monitor_evaluate_saved_media,
        )
    return _source_monitor_manager


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


def _external_url_preview_warnings(configuration: SourceProviderConfiguration) -> list[str]:
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
        return HTTPException(status_code=400, detail="Folder path metadata is required.")
    if reason == "folder_missing":
        return HTTPException(status_code=404, detail="Configured folder was not found.")
    if reason == "folder_not_directory":
        return HTTPException(status_code=400, detail="Configured folder must be a directory.")
    if reason == "folder_symlink":
        return HTTPException(status_code=400, detail="Configured folder must not be a symlink.")
    if reason == "folder_unavailable":
        return HTTPException(status_code=400, detail="Configured folder is unavailable.")
    return _media_import_error(error)


def _source_folder_import_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "folder_provider_required":
        return HTTPException(
            status_code=400,
            detail="Folder import requires a folder_import_future Source provider.",
        )
    if reason == "folder_required":
        return HTTPException(status_code=400, detail="Folder path metadata is required.")
    if reason == "folder_missing":
        return HTTPException(status_code=404, detail="Configured folder was not found.")
    if reason == "folder_not_directory":
        return HTTPException(status_code=400, detail="Configured folder must be a directory.")
    if reason == "folder_symlink":
        return HTTPException(status_code=400, detail="Configured folder must not be a symlink.")
    if reason == "folder_unavailable":
        return HTTPException(status_code=400, detail="Configured folder is unavailable.")
    if reason == "unsupported_copy_mode":
        return HTTPException(status_code=400, detail="Only copy_to_media_root is supported.")
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
        return HTTPException(status_code=400, detail="Detection proposal was already decided.")
    if reason == "unsupported_decision":
        return HTTPException(status_code=400, detail="Unsupported detection proposal decision.")
    return HTTPException(status_code=400, detail="Detection proposal could not be processed.")


def _model_adapter_error(error: ValueError) -> HTTPException:
    reason = str(error)
    if reason == "missing_adapter":
        return _not_found("Model adapter", "adapter")
    if reason == "adapter_mismatch":
        return HTTPException(status_code=400, detail="Adapter id in path and payload must match.")
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
    if reason == "unsupported_detector_output":
        return HTTPException(
            status_code=400,
            detail="Detector output format is not supported by this adapter path.",
        )
    if reason == "local_detector_failed":
        return HTTPException(status_code=500, detail="Local image detector failed unexpectedly.")
    if reason == "unsupported_media_type":
        return HTTPException(
            status_code=400,
            detail="Model adapter does not support this media type.",
        )
    return _detection_interface_error(error)


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
                "Saved snapshot could not be decoded locally. PNG works without extra "
                "dependencies; JPEG/WebP need an available local image decoder."
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
    return HTTPException(status_code=400, detail="Motion Evidence could not be processed.")


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
    return HTTPException(status_code=400, detail="SpeciesSuggestion could not be processed.")


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


def _motion_frame_score_response(frame_score: MotionFrameScore) -> MotionFrameScoreResponse:
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


def _motion_frame_score_from_payload(frame_score: MotionFrameScoreResponse) -> MotionFrameScore:
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
            if any(_auto_cell_blocked(candidate, blocked) for blocked in blocked_bounds):
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
    if blocked.left <= center_x <= blocked.right and blocked.top <= center_y <= blocked.bottom:
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

        cluster = _auto_motion_cluster(cluster_ids, cell_by_id, triggered_by_cell, config)
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
                cell_ids=[cell.region_id for cell in sorted(
                    cluster.cells,
                    key=lambda cell: (cell.row, cell.column),
                )],
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
            ratio for frame_index, ratio, _pixels in events if frame_index in group_frames
        )

    best_group = max(ready_groups, key=group_peak)
    best_group_frames = set(best_group)
    best_frame_index, peak_changed_ratio, _changed_pixels = max(
        (event for event in events if event[0] in best_group_frames),
        key=lambda event: event[1],
    )
    if (
        len(cells) == 1
        and peak_changed_ratio < _auto_isolated_cell_min_ratio(config.min_changed_ratio)
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
    vertical = "Upper" if center_y < 1 / 3 else "Lower" if center_y > 2 / 3 else "Center"
    horizontal = "left" if center_x < 1 / 3 else "right" if center_x > 2 / 3 else "center"
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
    return [
        ExistingActivityReference(
            activity_id=evidence.id,
            source_id=evidence.source_id,
            stream_id=evidence.stream_id,
            region_kind="zone",
            region_id=evidence.zone_id,
            created_at=evidence.created_at,
            snapshot_media_asset_id=evidence.snapshot_media_asset_id,
            status=evidence.status.value,
        )
        for evidence in evidence_items
    ]


def _frame_summary_for_media_asset(
    frames: list[SavedMediaFrameSummary],
    media_asset_id: str | None,
) -> SavedMediaFrameSummary | None:
    if media_asset_id is None:
        return None
    return next((frame for frame in frames if frame.media_asset_id == media_asset_id), None)


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
    return max(candidates, key=lambda candidate: candidate.peak_changed_ratio, default=None)


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


@app.post("/api/motion/extract-candidates", response_model=MotionExtractCandidatesResponse)
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


@app.post("/api/motion/evaluate-sequence", response_model=MotionEvaluateSequenceResponse)
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


@app.post("/api/motion/evaluate-saved-media", response_model=MotionEvaluateSavedMediaResponse)
async def evaluate_saved_media_motion(
    payload: MotionEvaluateSavedMediaRequest,
) -> MotionEvaluateSavedMediaResponse:
    # Saved snapshots are explicitly supplied by the user; this does no capture,
    # background source work, model inference, Event/Visit promotion, or truth writes.
    repository = get_repository()
    stream = repository.get_stream(payload.stream_id)
    if stream is None:
        raise _not_found("Stream", payload.stream_id)

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
            frame = load_saved_image_frame_plane(media_path, content_type=asset.content_type)
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
    requested_zone_ids = [zone_id for zone_id in payload.zone_ids or [] if zone_id.strip()]
    candidate_zones = (
        [zones_by_id[zone_id] for zone_id in requested_zone_ids if zone_id in zones_by_id]
        if requested_zone_ids
        else all_zones
    )
    missing_zone_ids = [zone_id for zone_id in requested_zone_ids if zone_id not in zones_by_id]
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
        _motion_candidate_response(candidate)
        for candidate in motion_candidates
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
    strongest_activity_area = (
        session_activity_area
        or (activity_area_by_id.get(strongest_zone_id) if strongest_zone_id else None)
    )
    best_activity_at = _media_datetime_for_frame(
        frame_summaries,
        frame_index=best_candidate.best_frame_index if best_candidate else None,
        frame_index_start=payload.frame_index_start,
    )
    session_region_kind = "auto_area" if uses_auto_regions else "zone"
    session_region_id = _activity_session_region_id(strongest_activity_area)
    existing_session_references = (
        _motion_evidence_session_references(
            repository.list_motion_evidence(zone_id=best_candidate.zone_id)
        )
        if best_candidate and not uses_auto_regions
        else []
    )
    can_create_review_activity = not uses_auto_regions
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
    crop_plan = (
        plan_activity_crop(
            source_media_asset_id=best_media_asset_id,
            image_width=best_snapshot_frame.width,
            image_height=best_snapshot_frame.height,
            left=strongest_activity_area.left if strongest_activity_area else None,
            top=strongest_activity_area.top if strongest_activity_area else None,
            right=strongest_activity_area.right if strongest_activity_area else None,
            bottom=strongest_activity_area.bottom if strongest_activity_area else None,
            crop_reason="auto_region_cluster" if uses_auto_regions else "user_zone",
        )
        if best_snapshot_frame is not None and best_media_asset_id is not None
        else None
    )
    created_evidence: list[MotionEvidenceResponse] = []
    if payload.create_motion_evidence and motion_candidates and uses_auto_regions:
        creation_skipped_reason = "auto_region_review_activity_requires_user_zone"
        warnings.append(
            "Automatic activity areas can detect motion now; review activity creation "
            "still requires a named Zone in this build."
        )
    elif (
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
                        zone_id=best_candidate.zone_id,
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
                            "max_snapshots_per_session": (
                                session_recommendation.max_snapshots_per_session
                            ),
                        },
                        snapshot_media_asset_id=(
                            best_media_asset_id if payload.attach_best_snapshot else None
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
        strongest_activity_area_id=(
            strongest_activity_area.area_id if strongest_activity_area else None
        ),
        strongest_activity_area_label=(
            strongest_activity_area.label if strongest_activity_area else None
        ),
        suppressed_auto_region_count=suppressed_auto_region_count,
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


@app.post("/api/motion/evidence", response_model=MotionEvidenceResponse, status_code=201)
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


@app.post("/api/motion/evidence/{evidence_id}/ignore", response_model=MotionEvidenceResponse)
async def ignore_motion_evidence(evidence_id: str) -> MotionEvidenceResponse:
    try:
        evidence = get_repository().ignore_motion_evidence(evidence_id)
    except ValueError as error:
        raise _motion_evidence_error(error) from error
    if evidence is None:
        raise _not_found("Motion Evidence", evidence_id)
    return evidence


@app.post("/api/species-suggestions", response_model=SpeciesSuggestionResponse, status_code=201)
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


@app.get("/api/species-suggestions/{suggestion_id}", response_model=SpeciesSuggestionResponse)
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


@app.get("/api/source-provider-definitions", response_model=list[SourceProviderDefinition])
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
async def get_source_provider_configuration(source_id: str) -> SourceProviderConfiguration:
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
        configuration = get_repository().update_source_provider_configuration(source_id, payload)
    except ValueError as error:
        if str(error) == "unknown_provider_key":
            raise HTTPException(status_code=400, detail="Unknown source provider key.") from error
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

    stream_id = _resolve_external_url_save_stream_id(repository, source_id, request.stream_id)
    result = external_url_preview.fetch_external_url_preview(
        url,
        timeout_seconds=request.timeout_seconds,
        max_bytes=request.max_bytes,
    )
    if result.status != "available" or result.fetched_bytes is None or result.fetched_at is None:
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
        status=result.status.value if hasattr(result.status, "value") else str(result.status),
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
            "left": strongest_area.left if strongest_area else None,
            "top": strongest_area.top if strongest_area else None,
            "right": strongest_area.right if strongest_area else None,
            "bottom": strongest_area.bottom if strongest_area else None,
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


def _monitor_review_unavailable_reason(result: MotionEvaluateSavedMediaResponse) -> str | None:
    if not result.activity_detected:
        return "no_activity_detected"
    if result.uses_auto_regions or not result.can_create_review_activity:
        return "auto_region_requires_named_zone"
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
        return "Activity detected. Create review activity when ready."
    if state.review_activity_unavailable_reason == "auto_region_requires_named_zone":
        return (
            "Activity detected in an automatic area. Add or select a named zone to "
            "create a review activity in this build."
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
            return "Monitoring is active. Activity detected on the latest motion check."
        if state.last_activity_detected is False:
            return "Monitoring is active. No activity detected on the latest motion check."
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


@app.post(
    "/api/streams/{stream_id}/monitor/start",
    response_model=SourceMonitorStatusResponse,
)
async def start_stream_monitor(
    stream_id: str,
    payload: SourceMonitorStartRequest | None = None,
) -> SourceMonitorStatusResponse:
    repository = get_repository()
    stream, _source = _stream_source_for_monitor(repository, stream_id)
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


@app.get("/api/sources/{source_id}/connection", response_model=SourceConnectionStatusResponse)
async def get_source_connection_status(source_id: str) -> SourceConnectionStatus:
    status = get_repository().get_source_connection_status(source_id)
    if status is None:
        raise _not_found("Source", source_id)
    return status


@app.get("/api/sources/{source_id}/setup-review", response_model=SourceSetupReviewResponse)
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


@app.get("/api/streams/{stream_id}", response_model=Stream)
async def get_stream(stream_id: str) -> Stream:
    stream = get_repository().get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return stream


@app.get("/api/streams/{stream_id}/playback", response_model=StreamPlaybackStatusResponse)
async def get_stream_playback_status(stream_id: str) -> StreamPlaybackStatus:
    status = get_repository().get_stream_playback_status(stream_id)
    if status is None:
        raise _not_found("Stream", stream_id)
    return status


@app.get("/api/streams/{stream_id}/live/rtsp-mjpeg")
async def get_stream_rtsp_mjpeg_bridge(stream_id: str) -> StreamingResponse:
    configuration = get_repository().get_stream_live_playback_config(stream_id)
    if configuration is None:
        raise _not_found("Stream", stream_id)
    if configuration.provider_key != "external_url":
        raise HTTPException(
            status_code=400,
            detail="RTSP bridge requires an external_url Source provider.",
        )
    if not configuration.live_stream_url:
        raise HTTPException(status_code=400, detail="Live stream URL is not configured.")
    if configuration.live_stream_type != "rtsp":
        raise HTTPException(status_code=400, detail="RTSP bridge requires RTSP stream type.")
    if not rtsp_bridge.validate_rtsp_url(configuration.live_stream_url):
        raise HTTPException(
            status_code=400,
            detail="RTSP bridge requires an rtsp:// or rtsps:// stream URL.",
        )
    if not rtsp_bridge.is_ffmpeg_available():
        raise HTTPException(status_code=503, detail="RTSP bridge unavailable: ffmpeg not found.")

    try:
        process = rtsp_bridge.start_rtsp_mjpeg_process(configuration.live_stream_url)
    except (OSError, ValueError):
        raise HTTPException(status_code=502, detail="RTSP live view failed to start.") from None

    return StreamingResponse(
        rtsp_bridge.iter_multipart_mjpeg(process),
        media_type=f"multipart/x-mixed-replace; boundary={rtsp_bridge.MJPEG_BOUNDARY}",
    )


@app.get("/api/streams/{stream_id}/live/local-mjpeg")
async def get_stream_local_mjpeg_bridge(stream_id: str) -> StreamingResponse:
    configuration = get_repository().get_stream_live_playback_config(stream_id)
    if configuration is None:
        raise _not_found("Stream", stream_id)
    if configuration.provider_key != "local_usb":
        raise HTTPException(
            status_code=400,
            detail="Local camera bridge requires a local_usb Source provider.",
        )
    if configuration.live_stream_type != local_camera_bridge.LOCAL_USB_STREAM_TYPE:
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

    try:
        process = local_camera_bridge.start_local_camera_mjpeg_process(
            configuration.local_camera_device or "",
            camera_format=configuration.local_camera_format,
        )
    except (OSError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Local camera device unavailable or playback failed.",
        ) from None

    return StreamingResponse(
        local_camera_bridge.iter_multipart_mjpeg(process),
        media_type=(
            f"multipart/x-mixed-replace; boundary={local_camera_bridge.MJPEG_BOUNDARY}"
        ),
    )


@app.get("/api/streams/{stream_id}/zones", response_model=list[Zone])
async def list_stream_zones(stream_id: str) -> list[Zone]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return repository.zones_for_stream(stream_id)


@app.get("/api/streams/{stream_id}/events", response_model=list[Event])
async def list_stream_events(stream_id: str) -> list[Event]:
    repository = get_repository()
    stream = repository.get_stream(stream_id)
    if stream is None:
        raise _not_found("Stream", stream_id)
    return repository.events_for_stream(stream_id)


@app.get("/api/zones", response_model=list[Zone])
async def list_zones() -> list[Zone]:
    return get_repository().list_zones()


@app.get("/api/zones/{zone_id}", response_model=Zone)
async def get_zone(zone_id: str) -> Zone:
    zone = get_repository().get_zone(zone_id)
    if zone is None:
        raise _not_found("Zone", zone_id)
    return zone


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
    return VisitDetail(
        visit=visit,
        event=event,
        stream=stream,
        primary_zone=(
            repository.get_zone(event.primary_zone_id)
            if event.primary_zone_id is not None
            else None
        ),
        detections=event.detections,
        motion_evidence=repository.motion_evidence_for_visit(visit.id),
        media_asset=repository.media_asset_for_path(visit.representative_media_path),
        detection_proposals=detection_proposals,
        detection_runs=_detection_runs_for_proposals(repository, detection_proposals),
        review_labels=(
            repository.review_labels_for_event(event.id)
            + repository.review_labels_for_visit(visit.id)
        ),
        dataset_ready=dataset_ready,
        review_summary=repository.review_summary_for_dataset_state(dataset_ready),
    )


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
async def preview_folder_import(payload: FolderImportPreviewRequest) -> FolderImportPreview:
    try:
        return get_repository().preview_folder_import(payload.folder_path)
    except ValueError as error:
        raise _folder_import_error(error) from error


@app.post("/api/media/folder-import", response_model=FolderImportResult, status_code=201)
async def import_folder_media(payload: FolderImportCreate) -> FolderImportResult:
    try:
        return get_repository().import_folder_media(payload)
    except ValueError as error:
        raise _folder_import_error(error) from error


@app.get("/api/media/saved-preview-retention", response_model=SavedMediaRetentionReportResponse)
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


@app.post("/api/media/{media_id}/cleanup-preview", response_model=SavedMediaCleanupResponse)
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
            headers={"content-disposition": f'attachment; filename="{asset.original_filename}"'},
        )
    return FileResponse(
        path,
        media_type=asset.content_type,
        filename=asset.original_filename,
    )


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


@app.post("/api/detection-runs/demo", response_model=DemoDetectionRunResult, status_code=201)
async def create_demo_detection_run(payload: DemoDetectionRunCreate) -> DemoDetectionRunResult:
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


@app.get("/api/detection-runs/{run_id}/proposals", response_model=list[DetectionProposal])
async def list_detection_run_proposals(run_id: str) -> list[DetectionProposal]:
    proposals = get_repository().detection_proposals_for_run(run_id)
    if proposals is None:
        raise _not_found("Detection run", run_id)
    return proposals


@app.get("/api/detection-proposals", response_model=list[DetectionProposal])
async def list_detection_proposals() -> list[DetectionProposal]:
    return get_repository().list_detection_proposals()


@app.post("/api/detection-proposals", response_model=DetectionProposal, status_code=201)
async def create_detection_proposal(payload: DetectionProposalCreate) -> DetectionProposal:
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
async def list_review_queue() -> list[ReviewQueueItem]:
    return get_repository().review_queue_items()


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
            raise HTTPException(status_code=400, detail="A correction label is required.") from error
        raise HTTPException(status_code=400, detail="Review Queue bulk correction failed.") from error


@app.get("/api/review-labels", response_model=list[ReviewLabel])
async def list_review_labels() -> list[ReviewLabel]:
    return get_repository().list_review_labels()


@app.post("/api/review-labels", response_model=ReviewCorrectionResult, status_code=201)
async def create_review_label(payload: ReviewCorrectionCreate) -> ReviewCorrectionResult:
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


@app.get("/api/dataset-exports/{export_id}/manifest", response_model=DatasetExportManifest)
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


@app.get("/api/classifier-training-manifest", response_model=ClassifierTrainingManifestResponse)
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


@app.get("/api/settings/local-data", response_model=LocalDataStatus)
async def get_local_data_status() -> LocalDataStatus:
    return get_repository().local_data_status()


@app.post("/api/settings/reset-demo-data", response_model=LocalDataStatus)
async def reset_demo_data() -> LocalDataStatus:
    # Local demo reset clears product metadata only; imported media files stay on disk.
    return get_repository().reset_demo_data()
