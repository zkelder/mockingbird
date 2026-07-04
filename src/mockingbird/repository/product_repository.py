"""Repository for persisted MockingBird product state."""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from mockingbird.api import demo_data
from mockingbird.detectors.local_image_detector import (
    LOCAL_IMAGE_DETECTOR_ID,
    LOCAL_DETECTOR_SETUP_HINT,
    SUPPORTED_IMAGE_CONTENT_TYPES,
    LocalDetectorConfigurationError,
    LocalDetectorOutputError,
    LocalDetectorRuntimeUnavailableError,
    LocalDetectorUnsupportedMediaError,
    LocalDetectorStatus,
    get_local_detector_status,
    run_local_image_detector,
)
from mockingbird.detectors.megadetector_adapter import (
    MEGADETECTOR_ADAPTER_ID,
    MEGADETECTOR_SETUP_HINT,
    MEGADETECTOR_SUPPORTED_LABELS,
    SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES,
    MegaDetectorConfigurationError,
    MegaDetectorModelFileError,
    MegaDetectorOutputError,
    MegaDetectorRuntimeUnavailableError,
    MegaDetectorStatus,
    MegaDetectorUnsupportedMediaError,
    get_megadetector_status,
    normalize_megadetector_label,
    run_megadetector_on_image,
)
from mockingbird.api.schemas import (
    AdapterEvaluationItem,
    AdapterEvaluationOutcome,
    AdapterEvaluationSummary,
    AnalyticsSummary,
    BoundingBox,
    CameraSource,
    ClassifierManifestExample,
    ClassifierManifestExportFile,
    ClassifierManifestFileExportRequest,
    ClassifierManifestFileExportResponse,
    ClassifierManifestSkippedRecord,
    ClassifierManifestPlannedMediaFile,
    ClassifierManifestSkippedMediaRecord,
    ClassifierManifestSummary,
    ClassifierManifestTaxonomyEntry,
    ClassifierReadinessReport,
    ClassifierReadinessSkipSummary,
    ClassifierReadinessSpeciesSummary,
    ClassifierTrainingManifestResponse,
    DatasetCoverageGap,
    DatasetCoverageSpecies,
    DatasetCoverageSummary,
    DatasetExport,
    DatasetExportCreate,
    DatasetExportDetail,
    DatasetExportManifest,
    DatasetExportRecord,
    DatasetQualityIssue,
    DatasetQualitySummary,
    DemoDetectionRunCreate,
    DemoDetectionRunResult,
    Detection,
    DetectionProposal,
    DetectionProposalCreate,
    DetectionProposalDecision,
    DetectionProposalDecisionCreate,
    DetectionProposalDecisionResult,
    DetectionProposalStatus,
    DetectionRun,
    DetectionRunCreate,
    DetectionRunStatus,
    DetectionSource,
    Event,
    ExportStatus,
    FolderImportCandidate,
    FolderImportCreate,
    FolderImportEvidenceBatchCreateItem,
    FolderImportEvidenceBatchCreateRequest,
    FolderImportEvidenceBatchCreateResponse,
    FolderImportEvidenceBatchDryRunItem,
    FolderImportEvidenceBatchDryRunRequest,
    FolderImportEvidenceBatchDryRunResponse,
    FolderImportPreview,
    FolderImportResult,
    FolderImportSkippedFile,
    LabelCategory,
    LocalDataStatus,
    MediaAsset,
    MediaImportResult,
    ModelAdapter,
    ModelAdapterConfigurationStatus,
    ModelAdapterKind,
    ModelReadinessChecklistItem,
    ModelReadinessSummary,
    ModelAdapterRunRequest,
    ModelAdapterRunResult,
    ModelAdapterStatus,
    MotionEvidenceCreateRequest,
    MotionEvidencePromoteRequest,
    MotionEvidencePromoteResponse,
    MotionEvidenceResponse,
    MotionEvidenceStatus,
    Point,
    ReviewCorrectionCreate,
    ReviewCorrectionResult,
    ReviewLabel,
    ReviewQueueItem,
    ReviewStatus,
    SavedMediaCleanupDryRunItem,
    SavedMediaCleanupDryRunRequest,
    SavedMediaCleanupDryRunResponse,
    SavedMediaCleanupRequest,
    SavedMediaCleanupResponse,
    SavedMediaRetentionItem,
    SavedMediaRetentionReportResponse,
    SavedMediaRetentionSummary,
    SavedPreviewMotionEvidenceRequest,
    SourceConnectionStatus,
    SourceConnectionStatusValue,
    SourceFolderImportCreatedMediaAsset,
    SourceFolderImportRequest,
    SourceFolderImportResponse,
    SourceFolderImportSkipped,
    SourceFolderImportPreviewCandidate,
    SourceFolderImportPreviewRequest,
    SourceFolderImportPreviewResponse,
    SourceFolderImportPreviewSkipped,
    SourceProviderConfiguration,
    SourceProviderConfigurationUpdate,
    SourceProviderDefinition,
    SourceProviderDefinitionStatus,
    SourceProviderField,
    SourceSetupReviewResponse,
    SourceSetupReviewStep,
    SourceSetupReviewStream,
    SpeciesSuggestionCreateRequest,
    SpeciesSuggestionResponse,
    SpeciesSuggestionStatus,
    SpeciesSuggestionStatusUpdateRequest,
    SourceKind,
    SourceProviderKind,
    SourceStatus,
    Stream,
    StreamPlaybackKind,
    StreamPlaybackStatus,
    StreamPlaybackStatusValue,
    TaxonomyLabel,
    Visit,
    WebhookPayloadCandidate,
    WebhookPayloadValidationRequest,
    WebhookPayloadValidationResponse,
    Zone,
    ZoneCreate,
    ZoneType,
    ZoneUpdate,
)
from mockingbird.source_providers import folder_import_preview
from mockingbird.source_providers.webhook_validation import classify_webhook_payload
from mockingbird.storage.database import (
    DEFAULT_DB_URL,
    create_database_engine,
    create_session_factory,
    initialize_database,
    resolve_media_root,
    resolve_database_url,
)
from mockingbird.storage.models import (
    Base,
    CameraSourceModel,
    DatasetExportModel,
    DetectionModel,
    DetectionProposalModel,
    DetectionRunModel,
    EventModel,
    MediaAssetModel,
    ReviewLabelModel,
    StreamModel,
    TaxonomyLabelModel,
    VisitModel,
    ZoneModel,
)

SUPPORTED_MEDIA_CONTENT_TYPES = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "video/mp4": "video",
    "video/quicktime": "video",
}

EXTERNAL_URL_PREVIEW_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

SUPPORTED_MEDIA_EXTENSIONS = {
    ".jpg": ("image/jpeg", "image"),
    ".jpeg": ("image/jpeg", "image"),
    ".png": ("image/png", "image"),
    ".webp": ("image/webp", "image"),
    ".mp4": ("video/mp4", "video"),
    ".mov": ("video/quicktime", "video"),
}

CLASSIFIER_MANIFEST_COPY_IMAGE_EXTENSIONS = {
    extension
    for extension, (_content_type, media_type) in SUPPORTED_MEDIA_EXTENSIONS.items()
    if media_type == "image"
}

DEFAULT_CLASSIFIER_MANIFEST_EXPORT_ROOT = Path("data/classifier_manifest_exports")

CLASSIFIER_MANIFEST_EXPORT_CONTENT_TYPES = {
    "manifest.jsonl": "application/x-ndjson",
    "manifest.csv": "text/csv",
    "taxonomy.json": "application/json",
    "skipped_records.jsonl": "application/x-ndjson",
    "summary.json": "application/json",
}

BASE_MODEL_ADAPTERS: tuple[ModelAdapter, ...] = (
    ModelAdapter(
        id="demo_rule_detector",
        name="Demo Rule Detector",
        kind=ModelAdapterKind.demo,
        status=ModelAdapterStatus.available,
        version="contract-1",
        description=(
            "Local-only demo adapter contract that creates proposal evidence "
            "without running media analysis."
        ),
        supported_media_types=["image", "video"],
        supported_labels=["unknown_bird", "bird", "squirrel", "cat", "unknown_animal"],
        creates_review_truth=False,
        local_only=True,
        notes="Future detector hook; review and correction remain required.",
    ),
)

SOURCE_PROVIDER_DEFINITIONS: tuple[SourceProviderDefinition, ...] = (
    SourceProviderDefinition(
        provider_key="demo",
        display_name="Demo source",
        description="Seeded local demo metadata for stream, zone, and review workflows.",
        status=SourceProviderDefinitionStatus.demo,
        supports_live_playback=False,
        supports_zone_editing=True,
        fields=[
            SourceProviderField(
                key="demo_seed",
                label="Demo seed",
                required=False,
                secret=False,
                description="Local seeded demo context.",
                placeholder="backyard-demo",
            )
        ],
    ),
    SourceProviderDefinition(
        provider_key="manual_media",
        display_name="Manual media",
        description="Metadata for sources that begin from manually supplied local media.",
        status=SourceProviderDefinitionStatus.available_contract_only,
        supports_live_playback=False,
        supports_zone_editing=True,
        fields=[
            SourceProviderField(
                key="source_label",
                label="Source label",
                required=False,
                secret=False,
                description="Optional label for grouping local media under this source.",
                placeholder="Backyard imports",
            )
        ],
    ),
    SourceProviderDefinition(
        provider_key="external_url",
        display_name="External URL / HTTP still-image",
        description="Metadata for explicit still-image preview/status; no live playback claim.",
        status=SourceProviderDefinitionStatus.available_contract_only,
        supports_live_playback=False,
        supports_zone_editing=True,
        fields=[
            SourceProviderField(
                key="url",
                label="URL",
                required=True,
                secret=False,
                description="Used only by explicit still-image preview fetch.",
                placeholder="http://camera.local/still.jpg",
            ),
            SourceProviderField(
                key="display_name",
                label="Display name",
                required=False,
                secret=False,
                description="Optional label for this still-image endpoint.",
                placeholder="Backyard still image",
            ),
            SourceProviderField(
                key="auth_username",
                label="Auth username",
                required=False,
                secret=True,
                description="Stored only as a configured/not-configured marker.",
                placeholder="Not used for preview fetch yet",
            ),
            SourceProviderField(
                key="auth_password",
                label="Auth password",
                required=False,
                secret=True,
                description="Stored only as a configured/not-configured marker.",
                placeholder="Not used for preview fetch yet",
            ),
            SourceProviderField(
                key="refresh_hint_seconds",
                label="Refresh hint seconds",
                required=False,
                secret=False,
                description="Metadata only; does not schedule polling.",
                placeholder="60",
            ),
            SourceProviderField(
                key="notes",
                label="Notes",
                required=False,
                secret=False,
                description="Optional local setup context.",
                placeholder="Still-image endpoint for the feeder view",
            ),
        ],
    ),
    SourceProviderDefinition(
        provider_key="rtsp_future",
        display_name="RTSP future provider",
        description="Future provider contract for network camera-style streams.",
        status=SourceProviderDefinitionStatus.future_adapter,
        supports_live_playback=False,
        supports_zone_editing=True,
        fields=[
            SourceProviderField(
                key="url",
                label="URL",
                required=True,
                secret=False,
                description="Stored as metadata only; no network validation is performed.",
                placeholder="rtsp://camera.local/stream",
            ),
            SourceProviderField(
                key="username",
                label="Username",
                required=False,
                secret=False,
                description="Optional provider username metadata.",
                placeholder="viewer",
            ),
            SourceProviderField(
                key="access_secret",
                label="Access secret",
                required=False,
                secret=True,
                description="Stored only as a configured/not-configured marker.",
                placeholder="Not stored raw",
            ),
        ],
    ),
    SourceProviderDefinition(
        provider_key="esp32_future",
        display_name="ESP32 future provider",
        description="Future provider contract for small outdoor camera devices.",
        status=SourceProviderDefinitionStatus.future_adapter,
        supports_live_playback=False,
        supports_zone_editing=True,
        fields=[
            SourceProviderField(
                key="device_url",
                label="Device URL",
                required=True,
                secret=False,
                description="Stored as metadata only; MockingBird will not connect yet.",
                placeholder="http://device.local",
            ),
            SourceProviderField(
                key="access_token",
                label="Access token",
                required=False,
                secret=True,
                description="Stored only as a configured/not-configured marker.",
                placeholder="Not stored raw",
            ),
        ],
    ),
    SourceProviderDefinition(
        provider_key="browser_camera_future",
        display_name="Browser camera future provider",
        description="Future provider contract for a browser-mediated local camera source.",
        status=SourceProviderDefinitionStatus.future_adapter,
        supports_live_playback=False,
        supports_zone_editing=True,
        fields=[
            SourceProviderField(
                key="device_label",
                label="Device label",
                required=False,
                secret=False,
                description="Optional user-facing device label.",
                placeholder="Back porch camera",
            )
        ],
    ),
    SourceProviderDefinition(
        provider_key="folder_import_future",
        display_name="Folder / trail-cam import",
        description=(
            "Metadata for explicit local folder or trail-cam preview/import; "
            "imports create MediaAssets only and no live playback."
        ),
        status=SourceProviderDefinitionStatus.future_adapter,
        supports_live_playback=False,
        supports_zone_editing=True,
        fields=[
            SourceProviderField(
                key="folder_path",
                label="Folder path",
                required=True,
                secret=True,
                description=(
                    "Local folder, SD-card dump, NAS folder, or trail-cam export location."
                ),
                placeholder="/path/to/trailcam/folder",
            ),
            SourceProviderField(
                key="display_name",
                label="Display name",
                required=False,
                secret=False,
                description="Optional label for this folder/trail-cam source.",
                placeholder="Backyard trail cam",
            ),
            SourceProviderField(
                key="recursive",
                label="Recursive",
                required=False,
                secret=False,
                description="Metadata string only; parsing is future work.",
                placeholder="false",
            ),
            SourceProviderField(
                key="allowed_extensions",
                label="Allowed extensions",
                required=False,
                secret=False,
                description="Metadata string only; parsing is future work.",
                placeholder="jpg,jpeg,png,webp",
            ),
            SourceProviderField(
                key="default_stream_id",
                label="Default stream ID",
                required=False,
                secret=False,
                description="Optional related Stream context for future imports.",
                placeholder="stream-backyard-feeder",
            ),
            SourceProviderField(
                key="default_zone_id",
                label="Default zone ID",
                required=False,
                secret=False,
                description="Optional related Zone context for future imports.",
                placeholder="zone-feeder",
            ),
            SourceProviderField(
                key="import_mode",
                label="Import mode",
                required=False,
                secret=False,
                description="Metadata only; future implementation decides behavior.",
                placeholder="media_only",
            ),
            SourceProviderField(
                key="notes",
                label="Notes",
                required=False,
                secret=False,
                description="Optional local setup context.",
                placeholder="SD-card dump from the back fence trail cam",
            ),
        ],
    ),
    SourceProviderDefinition(
        provider_key="webhook_future",
        display_name="Generic webhook ingest",
        description=(
            "Metadata for future signed webhook ingest; no endpoint accepts payloads yet."
        ),
        status=SourceProviderDefinitionStatus.future_adapter,
        supports_live_playback=False,
        supports_zone_editing=True,
        fields=[
            SourceProviderField(
                key="endpoint_name",
                label="Endpoint name",
                required=False,
                secret=False,
                description="Optional local label for the future webhook endpoint.",
                placeholder="backyard-webhook",
            ),
            SourceProviderField(
                key="shared_secret_configured",
                label="Shared secret",
                required=True,
                secret=True,
                description="Marker for future signed webhook ingest.",
                placeholder="configured later",
            ),
            SourceProviderField(
                key="allowed_source_name",
                label="Allowed source name",
                required=False,
                secret=False,
                description="Optional external source name filter for future payload validation.",
                placeholder="backyard-camera",
            ),
            SourceProviderField(
                key="default_stream_id",
                label="Default stream ID",
                required=False,
                secret=False,
                description="Optional Stream context metadata for future webhook payloads.",
                placeholder="stream-backyard-feeder",
            ),
            SourceProviderField(
                key="default_zone_id",
                label="Default zone ID",
                required=False,
                secret=False,
                description="Optional Zone context metadata for future webhook payloads.",
                placeholder="zone-feeder",
            ),
            SourceProviderField(
                key="accept_media_uploads",
                label="Accept media uploads",
                required=False,
                secret=False,
                description="Metadata string only; parsing is future work.",
                placeholder="false",
            ),
            SourceProviderField(
                key="accept_media_urls",
                label="Accept media URLs",
                required=False,
                secret=False,
                description="Metadata string only; parsing is future work.",
                placeholder="false",
            ),
            SourceProviderField(
                key="notes",
                label="Notes",
                required=False,
                secret=False,
                description="Optional local setup context.",
                placeholder="Future local webhook source for feeder alerts",
            ),
        ],
    ),
)


@dataclass
class _CoverageAccumulator:
    label: str
    display_name: str
    category: str
    is_species: bool
    reviewed_record_count: int = 0
    export_ready_count: int = 0
    needs_review_count: int = 0
    unknown_count: int = 0
    media_asset_count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass(frozen=True)
class _SavedMediaMotionEvidenceResult:
    evidence: MotionEvidenceResponse
    warnings: list[str]
    duplicate_skipped: bool = False
    existing_motion_evidence_id: str | None = None
    provenance_kind: str | None = None


class MotionEvidenceModel(Base):
    __tablename__ = "motion_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("camera_sources.id"), nullable=True)
    stream_id: Mapped[str | None] = mapped_column(ForeignKey("streams.id"), nullable=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"), nullable=False)
    start_frame_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_frame_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_frame_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time: Mapped[str | None] = mapped_column(String, nullable=True)
    end_time: Mapped[str | None] = mapped_column(String, nullable=True)
    best_frame_time: Mapped[str | None] = mapped_column(String, nullable=True)
    peak_changed_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    triggered_frame_count: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_config_json: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_media_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_assets.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    promoted_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    promoted_visit_id: Mapped[str | None] = mapped_column(ForeignKey("visits.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SpeciesSuggestionModel(Base):
    __tablename__ = "species_suggestions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("camera_sources.id"), nullable=True)
    stream_id: Mapped[str | None] = mapped_column(ForeignKey("streams.id"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    visit_id: Mapped[str | None] = mapped_column(ForeignKey("visits.id"), nullable=True)
    media_asset_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)
    motion_evidence_id: Mapped[str | None] = mapped_column(
        ForeignKey("motion_evidence.id"),
        nullable=True,
    )
    adapter_id: Mapped[str] = mapped_column(String, nullable=False)
    adapter_name: Mapped[str] = mapped_column(String, nullable=False)
    suggested_label: Mapped[str] = mapped_column(String, nullable=False)
    suggested_common_name: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_scientific_name: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    alternatives_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_region_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceProviderConfigurationModel(Base):
    __tablename__ = "source_provider_configurations"

    source_id: Mapped[str] = mapped_column(ForeignKey("camera_sources.id"), primary_key=True)
    provider_key: Mapped[str] = mapped_column(String, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProductRepository:
    """Persist product-level stream, zone, event, review, and export state.

    Source adapters will normalize activity into these tables later; they do not
    define the core product model.
    """

    def __init__(
        self,
        db_url: str | None = None,
        engine: Engine | None = None,
        media_root: str | Path | None = None,
        classifier_manifest_export_root: str | Path | None = None,
    ) -> None:
        self.db_url = resolve_database_url(db_url)
        self.media_root = resolve_media_root(media_root)
        self.classifier_manifest_export_root = Path(
            classifier_manifest_export_root or DEFAULT_CLASSIFIER_MANIFEST_EXPORT_ROOT
        )
        self.engine = engine or create_database_engine(self.db_url)
        initialize_database(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self.seed_if_empty()

    def seed_if_empty(self) -> None:
        with self.session_factory() as session:
            with session.begin():
                self._seed_taxonomy_labels(session)
                source_count = session.scalar(select(func.count(CameraSourceModel.id))) or 0
                if source_count > 0:
                    return
                self._seed_session(session)

    def reset_demo_data(self) -> LocalDataStatus:
        # This clears local product metadata and reseeds demo state. It does not
        # delete media files or touch anything outside the configured database.
        with self.session_factory() as session:
            with session.begin():
                for model in (
                    SpeciesSuggestionModel,
                    SourceProviderConfigurationModel,
                    MotionEvidenceModel,
                    DetectionProposalModel,
                    DetectionRunModel,
                    MediaAssetModel,
                    DetectionModel,
                    VisitModel,
                    ReviewLabelModel,
                    DatasetExportModel,
                    EventModel,
                    ZoneModel,
                    StreamModel,
                    CameraSourceModel,
                ):
                    session.execute(delete(model))
                self._seed_taxonomy_labels(session)
                self._seed_session(session)
            return self._local_data_status(session)

    def local_data_status(self) -> LocalDataStatus:
        with self.session_factory() as session:
            return self._local_data_status(session)

    def _seed_session(self, session: Session) -> None:
        (
            sources,
            streams,
            zones,
            events,
            visits,
            review_labels,
            dataset_exports,
        ) = demo_data.seed_product_data()

        session.add_all(
            [
                CameraSourceModel(
                    id=source.id,
                    name=source.name,
                    kind=source.kind.value,
                    status=source.status.value,
                    description=source.description,
                )
                for source in sources
            ]
        )
        session.add_all(
            [
                StreamModel(
                    id=stream.id,
                    source_id=stream.source_id,
                    name=stream.name,
                    description=stream.description,
                    is_live=stream.is_live,
                )
                for stream in streams
            ]
        )
        session.add_all(
            [
                ZoneModel(
                    id=zone.id,
                    stream_id=zone.stream_id,
                    name=zone.name,
                    zone_type=zone.zone_type.value,
                    polygon_json=_points_to_json(zone.polygon),
                    is_active=zone.is_active,
                )
                for zone in zones
            ]
        )
        session.add_all(
            [
                EventModel(
                    id=event.id,
                    stream_id=event.stream_id,
                    title=event.title,
                    event_type=event.event_type,
                    started_at=event.started_at,
                    ended_at=event.ended_at,
                    primary_zone_id=event.primary_zone_id,
                    review_status=event.review_status.value,
                )
                for event in events
            ]
        )
        session.add_all(
            [
                DetectionModel(
                    id=detection.id,
                    event_id=event.id,
                    label=detection.label,
                    confidence=detection.confidence,
                    zone_id=detection.zone_id,
                    bbox_json=_bbox_to_json(detection.bbox),
                )
                for event in events
                for detection in event.detections
            ]
        )
        session.add_all(
            [
                VisitModel(
                    id=visit.id,
                    event_id=visit.event_id,
                    subject_label=visit.subject_label,
                    species_guess=visit.species_guess,
                    confidence=visit.confidence,
                    reviewed_label=visit.reviewed_label,
                    review_status=visit.review_status.value,
                    representative_media_path=visit.representative_media_path,
                )
                for visit in visits
            ]
        )
        session.add_all(
            [
                ReviewLabelModel(
                    id=label.id,
                    target_type=label.target_type,
                    target_id=label.target_id,
                    label=label.label,
                    notes=label.notes,
                    created_at=label.created_at,
                )
                for label in review_labels
            ]
        )
        session.add_all(
            [
                DatasetExportModel(
                    id=dataset_export.id,
                    name=dataset_export.name,
                    status=dataset_export.status.value,
                    reviewed_only=dataset_export.reviewed_only,
                    include_detections=dataset_export.include_detections,
                    include_zone_context=dataset_export.include_zone_context,
                    record_count=dataset_export.record_count,
                    created_at=dataset_export.created_at,
                )
                for dataset_export in dataset_exports
            ]
        )

    def _seed_taxonomy_labels(self, session: Session) -> None:
        # Taxonomy prepares future classifiers while keeping user corrections as truth.
        for label in demo_data.seed_taxonomy_labels():
            existing = session.get(TaxonomyLabelModel, label.id)
            if existing is None:
                session.add(
                    TaxonomyLabelModel(
                        id=label.id,
                        label=label.label,
                        display_name=label.display_name,
                        category=label.category.value,
                        scientific_name=label.scientific_name,
                        aliases_json=json.dumps(label.aliases),
                        is_species=label.is_species,
                        is_reviewable=label.is_reviewable,
                        sort_order=label.sort_order,
                    )
                )
                continue

            existing.label = label.label
            existing.display_name = label.display_name
            existing.category = label.category.value
            existing.scientific_name = label.scientific_name
            existing.aliases_json = json.dumps(label.aliases)
            existing.is_species = label.is_species
            existing.is_reviewable = label.is_reviewable
            existing.sort_order = label.sort_order

    def _local_data_status(self, session: Session) -> LocalDataStatus:
        analytics = self._analytics_summary(session)
        return LocalDataStatus(
            database_url=self.db_url,
            database_path=_database_path_from_url(self.db_url),
            using_default_database=self.db_url == DEFAULT_DB_URL,
            source_count=self._count(session, CameraSourceModel),
            stream_count=self._count(session, StreamModel),
            zone_count=self._count(session, ZoneModel),
            event_count=analytics.event_count,
            visit_count=analytics.visit_count,
            media_asset_count=self._count(session, MediaAssetModel),
            detection_run_count=self._count(session, DetectionRunModel),
            detection_proposal_count=self._count(session, DetectionProposalModel),
            motion_evidence_count=self._count(session, MotionEvidenceModel),
            review_label_count=self._count(session, ReviewLabelModel),
            dataset_export_count=self._count(session, DatasetExportModel),
            needs_review_count=analytics.needs_review_count,
            database_ready=True,
            seed_data_present=session.get(CameraSourceModel, demo_data.SOURCE_ID) is not None,
            local_first_note=(
                "MockingBird stores local product metadata, zones, corrections, "
                "review state, imported media references, analytics inputs, and "
                "dataset export manifests here. Imported media stays local and is "
                "not analyzed or transcoded in this phase."
            ),
        )

    def _count(self, session: Session, model: type) -> int:
        return session.scalar(select(func.count(model.id))) or 0

    def list_taxonomy_labels(self) -> list[TaxonomyLabel]:
        with self.session_factory() as session:
            labels = session.scalars(
                select(TaxonomyLabelModel).order_by(
                    TaxonomyLabelModel.sort_order,
                    TaxonomyLabelModel.id,
                )
            ).all()
            return [_taxonomy_label_from_model(label) for label in labels]

    def get_taxonomy_label(self, label: str) -> TaxonomyLabel | None:
        with self.session_factory() as session:
            model = self._taxonomy_label_model_for_input(session, label)
            return _taxonomy_label_from_model(model) if model else None

    def normalize_label(self, input_label: str) -> str:
        with self.session_factory() as session:
            return self._normalize_label_from_session(session, input_label)

    def label_suggestions(
        self,
        query: str | None = None,
        category: str | None = None,
    ) -> list[TaxonomyLabel]:
        with self.session_factory() as session:
            labels = session.scalars(
                select(TaxonomyLabelModel).order_by(
                    TaxonomyLabelModel.sort_order,
                    TaxonomyLabelModel.id,
                )
            ).all()
            query_key = _taxonomy_key(query or "")
            normalized_category = (category or "").strip().lower()
            suggestions: list[TaxonomyLabel] = []
            for label in labels:
                taxonomy_label = _taxonomy_label_from_model(label)
                if normalized_category:
                    if normalized_category == "species":
                        if not taxonomy_label.is_species:
                            continue
                    elif taxonomy_label.category.value != normalized_category:
                        continue

                if query_key:
                    search_values = [
                        taxonomy_label.id,
                        taxonomy_label.label,
                        taxonomy_label.display_name,
                        *taxonomy_label.aliases,
                    ]
                    if not any(query_key in _taxonomy_key(value) for value in search_values):
                        continue

                suggestions.append(taxonomy_label)
            return suggestions

    def list_sources(self) -> list[CameraSource]:
        with self.session_factory() as session:
            sources = session.scalars(select(CameraSourceModel).order_by(CameraSourceModel.id)).all()
            return [_source_from_model(source) for source in sources]

    def get_source(self, source_id: str) -> CameraSource | None:
        with self.session_factory() as session:
            source = session.get(CameraSourceModel, source_id)
            return _source_from_model(source) if source else None

    def list_source_provider_definitions(self) -> list[SourceProviderDefinition]:
        return list(SOURCE_PROVIDER_DEFINITIONS)

    def get_source_provider_configuration(
        self,
        source_id: str,
    ) -> SourceProviderConfiguration | None:
        with self.session_factory() as session:
            source = session.get(CameraSourceModel, source_id)
            if source is None:
                return None
            model = session.get(SourceProviderConfigurationModel, source_id)
            stream_ids = self._stream_ids_for_source(session, source_id)
            return _source_provider_configuration_from_model(source, model, stream_ids)

    def update_source_provider_configuration(
        self,
        source_id: str,
        payload: SourceProviderConfigurationUpdate,
    ) -> SourceProviderConfiguration | None:
        definition = _source_provider_definition(payload.provider_key)
        if definition is None:
            raise ValueError("unknown_provider_key")

        sanitized_config = _sanitize_source_provider_config(definition, payload.config)
        with self.session_factory() as session:
            with session.begin():
                source = session.get(CameraSourceModel, source_id)
                if source is None:
                    return None
                model = session.get(SourceProviderConfigurationModel, source_id)
                if model is None:
                    model = SourceProviderConfigurationModel(
                        source_id=source_id,
                        provider_key=payload.provider_key,
                        config_json=json.dumps(sanitized_config, sort_keys=True),
                        updated_at=datetime.now(UTC),
                    )
                    session.add(model)
                else:
                    model.provider_key = payload.provider_key
                    model.config_json = json.dumps(sanitized_config, sort_keys=True)
                    model.updated_at = datetime.now(UTC)
                session.flush()
                stream_ids = self._stream_ids_for_source(session, source_id)
                return _source_provider_configuration_from_model(source, model, stream_ids)

    def preview_source_folder_import(
        self,
        source_id: str,
        payload: SourceFolderImportPreviewRequest,
    ) -> SourceFolderImportPreviewResponse | None:
        with self.session_factory() as session:
            source = session.get(CameraSourceModel, source_id)
            if source is None:
                return None

            stream_ids = self._stream_ids_for_source(session, source_id)
            model = session.get(SourceProviderConfigurationModel, source_id)
            configuration = _source_provider_configuration_from_model(source, model, stream_ids)
            if configuration.provider_key != "folder_import_future":
                raise ValueError("folder_provider_required")

            config = json.loads(model.config_json) if model is not None else {}
            folder_path = (config.get("folder_path") or "").strip()
            config_recursive = _source_provider_bool(config.get("recursive"))
            config_allowed = _source_provider_list(config.get("allowed_extensions"))

        recursive = payload.recursive if payload.recursive is not None else config_recursive
        allowed_extensions = (
            payload.allowed_extensions
            if payload.allowed_extensions is not None
            else config_allowed
        )

        if not folder_path or folder_path == "configured":
            normalized_allowed, warnings = folder_import_preview.normalize_allowed_extensions(
                allowed_extensions
            )
            return SourceFolderImportPreviewResponse(
                source_id=source_id,
                provider_key="folder_import_future",
                folder_configured=False,
                recursive=recursive,
                allowed_extensions=normalized_allowed,
                candidates=[],
                skipped=[],
                total_candidates=0,
                total_skipped=0,
                total_known_bytes=0,
                unknown_size_count=0,
                scanned_at=datetime.now(UTC),
                dry_run=True,
                creates_media_assets=False,
                creates_events=False,
                creates_visits=False,
                creates_truth=False,
                warnings=[
                    "Folder path metadata is not configured; no folder was scanned.",
                    *warnings,
                ],
            )

        preview = folder_import_preview.preview_folder_import(
            folder_path,
            recursive=recursive,
            allowed_extensions=allowed_extensions,
            max_files=payload.max_files,
            max_depth=payload.max_depth,
        )
        return _source_folder_import_preview_response(
            source_id=source_id,
            preview=preview,
        )

    def import_source_folder_media_assets(
        self,
        source_id: str,
        payload: SourceFolderImportRequest,
    ) -> SourceFolderImportResponse | None:
        if payload.copy_mode != "copy_to_media_root":
            raise ValueError("unsupported_copy_mode")

        with self.session_factory() as session:
            source = session.get(CameraSourceModel, source_id)
            if source is None:
                return None

            stream_ids = self._stream_ids_for_source(session, source_id)
            model = session.get(SourceProviderConfigurationModel, source_id)
            configuration = _source_provider_configuration_from_model(source, model, stream_ids)
            if configuration.provider_key != "folder_import_future":
                raise ValueError("folder_provider_required")

            config = json.loads(model.config_json) if model is not None else {}
            folder_path = (config.get("folder_path") or "").strip()
            if not folder_path or folder_path == "configured":
                raise ValueError("folder_required")
            config_recursive = _source_provider_bool(config.get("recursive"))
            config_allowed = _source_provider_list(config.get("allowed_extensions"))
            config_stream_id = _clean_optional_text(config.get("default_stream_id"))
            config_zone_id = _clean_optional_text(config.get("default_zone_id"))

        recursive = payload.recursive if payload.recursive is not None else config_recursive
        allowed_extensions = (
            payload.allowed_extensions
            if payload.allowed_extensions is not None
            else config_allowed
        )
        selected_paths = (
            [path for path in payload.relative_paths if path.strip()]
            if payload.relative_paths is not None
            else None
        )
        if selected_paths is not None:
            preview = folder_import_preview.preview_folder_import_relative_paths(
                folder_path,
                selected_paths,
                allowed_extensions=allowed_extensions,
            )
        else:
            preview = folder_import_preview.preview_folder_import(
                folder_path,
                recursive=recursive,
                allowed_extensions=allowed_extensions,
                max_files=payload.max_files,
                max_depth=payload.max_depth,
            )

        imported_at = datetime.now(UTC)
        imported: list[SourceFolderImportCreatedMediaAsset] = []
        skipped = [
            SourceFolderImportSkipped(
                relative_path=item.relative_path,
                file_name=item.file_name,
                reason=item.reason,
                message=item.message,
            )
            for item in preview.skipped
        ]
        warnings = list(preview.warnings)
        total_bytes_copied = 0
        requested_stream_id = _clean_optional_text(payload.default_stream_id) or config_stream_id
        requested_zone_id = _clean_optional_text(payload.default_zone_id) or config_zone_id
        note = _clean_optional_text(payload.note)

        with self.session_factory() as session:
            with session.begin():
                stream_model, stream_warning = self._resolve_source_import_stream(
                    session,
                    source_id=source_id,
                    stream_id=requested_stream_id,
                )
                if stream_warning is not None:
                    warnings.append(stream_warning)
                zone_model = self._resolve_source_import_zone(
                    session,
                    zone_id=requested_zone_id,
                    stream_id=stream_model.id,
                )

                for candidate in preview.candidates:
                    content_type, media_type = SUPPORTED_MEDIA_EXTENSIONS[candidate.extension]
                    if self._folder_import_duplicate_exists(
                        session,
                        source_id=source_id,
                        relative_source_path=candidate.relative_path,
                        size_bytes=candidate.size_bytes,
                        modified_at=candidate.modified_at,
                    ):
                        skipped.append(
                            SourceFolderImportSkipped(
                                relative_path=candidate.relative_path,
                                file_name=candidate.file_name,
                                reason="already_imported",
                                message="This source file was already imported.",
                            )
                        )
                        continue

                    media_id = self._next_id(session, MediaAssetModel, "media-asset")
                    destination_name = (
                        f"{media_id}-folder-import-{_safe_filename(candidate.file_name)}"
                    )
                    try:
                        filename, local_path = self._copy_media_file(
                            destination_name,
                            candidate.source_path,
                        )
                        copied_size = local_path.stat().st_size
                    except OSError:
                        skipped.append(
                            SourceFolderImportSkipped(
                                relative_path=candidate.relative_path,
                                file_name=candidate.file_name,
                                reason="copy_error",
                                message="File could not be copied into local media storage.",
                            )
                        )
                        continue

                    asset_model = MediaAssetModel(
                        id=media_id,
                        source_id=source_id,
                        stream_id=stream_model.id,
                        filename=filename,
                        content_type=content_type,
                        media_type=media_type,
                        local_path=str(local_path),
                        original_filename=candidate.file_name,
                        file_size_bytes=copied_size,
                        created_at=imported_at,
                        notes=_folder_import_media_notes(
                            source_id=source_id,
                            stream_id=stream_model.id,
                            zone_id=zone_model.id if zone_model else None,
                            relative_source_path=candidate.relative_path,
                            original_filename=candidate.file_name,
                            size_bytes=candidate.size_bytes,
                            modified_at=candidate.modified_at,
                            imported_at=imported_at,
                            copy_mode=payload.copy_mode,
                            note=note,
                        ),
                    )
                    session.add(asset_model)
                    session.flush()
                    imported.append(
                        SourceFolderImportCreatedMediaAsset(
                            media_asset_id=media_id,
                            relative_source_path=candidate.relative_path,
                            file_name=candidate.file_name,
                            content_type=content_type,
                            size_bytes=copied_size,
                            stream_id=stream_model.id,
                            zone_id=zone_model.id if zone_model else None,
                            warnings=list(candidate.warnings),
                        )
                    )
                    total_bytes_copied += copied_size

        return SourceFolderImportResponse(
            source_id=source_id,
            provider_key="folder_import_future",
            imported=imported,
            skipped=skipped,
            total_imported=len(imported),
            total_skipped=len(skipped),
            total_bytes_copied=total_bytes_copied,
            imported_at=imported_at,
            copy_mode=payload.copy_mode,
            creates_media_assets=bool(imported),
            creates_motion_evidence=False,
            creates_events=False,
            creates_visits=False,
            creates_truth=False,
            warnings=warnings,
        )

    def get_source_connection_status(self, source_id: str) -> SourceConnectionStatus | None:
        with self.session_factory() as session:
            source = session.get(CameraSourceModel, source_id)
            if source is None:
                return None

            stream_ids = self._stream_ids_for_source(session, source_id)
            supports_zone_editing = len(stream_ids) > 0
            model = session.get(SourceProviderConfigurationModel, source_id)
            configuration = _source_provider_configuration_from_model(source, model, stream_ids)
            definition = _source_provider_definition(configuration.provider_key)
            provider_kind = _source_provider_kind(configuration.provider_key)

            if source.status == SourceStatus.disconnected.value:
                status = SourceConnectionStatusValue.offline
                message = "This source is offline, so streams can show only placeholders."
                setup_hint = "Save provider metadata now; playback still requires a future provider."
            elif configuration.provider_key == "demo":
                status = SourceConnectionStatusValue.demo
                message = (
                    "This source uses local demo metadata and demo stream panels; "
                    "no real playback provider is connected yet."
                )
                setup_hint = (
                    "Future source providers will feed this contract while streams "
                    "and zones stay product-level."
                )
            elif configuration.missing_fields:
                status = SourceConnectionStatusValue.not_configured
                if configuration.provider_key == "folder_import_future":
                    message = (
                        "This source needs folder path metadata before explicit folder "
                        "preview/import can run."
                    )
                    setup_hint = (
                        "Add folder path metadata; MockingBird will not scan or import folders "
                        "from status."
                    )
                elif configuration.provider_key == "webhook_future":
                    message = (
                        "This source needs shared secret metadata before future webhook "
                        "validation or ingest can be implemented."
                    )
                    setup_hint = (
                        "Add shared secret metadata; MockingBird does not accept webhook "
                        "payloads yet."
                    )
                else:
                    message = (
                        "This source still needs provider metadata before a future provider can run."
                    )
                    setup_hint = configuration.setup_hint
            elif configuration.provider_key == "folder_import_future":
                status = SourceConnectionStatusValue.configured
                message = (
                    "Folder/trail-cam metadata is configured for explicit preview/import. "
                    "Folder import creates MediaAssets only, and live playback is not "
                    "expected for this provider."
                )
                setup_hint = (
                    "Preview or import folder media explicitly; evidence/review handoff "
                    "requires future scope."
                )
            elif configuration.provider_key == "webhook_future":
                status = SourceConnectionStatusValue.configured
                message = (
                    "Webhook metadata is configured for future signed ingest. "
                    "No webhook ingest endpoint accepts inbound payloads yet."
                )
                setup_hint = (
                    "Future webhook ingest endpoint implementation is required before "
                    "MockingBird can receive payloads."
                )
            elif definition is not None and definition.status == SourceProviderDefinitionStatus.future_adapter:
                status = SourceConnectionStatusValue.configured
                message = (
                    "Provider configuration metadata is saved. MockingBird will not connect "
                    "to this Source yet."
                )
                setup_hint = "Live playback requires a future provider implementation."
            elif provider_kind == SourceProviderKind.manual_media:
                status = SourceConnectionStatusValue.configured
                message = (
                    "Manual media provider metadata is ready for explicit local imports; "
                    "live playback is not expected for this provider."
                )
                setup_hint = (
                    "Import media for a related Source/Stream, then review and correct "
                    "Events/Visits before export."
                )
            elif provider_kind == SourceProviderKind.external_url:
                status = SourceConnectionStatusValue.configured
                message = (
                    "External URL metadata is ready for explicit still-image preview fetch; "
                    "live playback is not implemented."
                )
                setup_hint = "Fetch a still-image preview explicitly; zone editing can continue."
            else:
                status = SourceConnectionStatusValue.configured
                message = (
                    "Provider configuration metadata is saved. MockingBird will not connect "
                    "to this Source yet."
                )
                setup_hint = "Zone editing can continue while playback remains unavailable."

            return SourceConnectionStatus(
                source_id=source.id,
                status=status,
                provider_kind=provider_kind,
                display_title=source.name,
                message=message,
                setup_hint=setup_hint,
                supports_streams=len(stream_ids) > 0,
                supports_live_playback=False,
                supports_zone_editing=supports_zone_editing,
                adapter_key=configuration.provider_key,
                configured_fields=configuration.configured_fields,
                missing_fields=configuration.missing_fields,
                stream_ids=stream_ids,
            )

    def get_source_setup_review(self, source_id: str) -> SourceSetupReviewResponse | None:
        source = self.get_source(source_id)
        if source is None:
            return None

        configuration = self.get_source_provider_configuration(source_id)
        connection = self.get_source_connection_status(source_id)
        if configuration is None or connection is None:
            return None

        definition = _source_provider_definition(configuration.provider_key)
        provider_display_name = (
            definition.display_name if definition is not None else configuration.provider_key
        )
        streams = [
            playback
            for stream in self.streams_for_source(source_id)
            if (playback := self.get_stream_playback_status(stream.id)) is not None
        ]
        return _source_setup_review_from_contracts(
            source=source,
            configuration=configuration,
            connection=connection,
            provider_display_name=provider_display_name,
            definition=definition,
            streams=streams,
        )

    def validate_webhook_payload(
        self,
        source_id: str,
        payload: WebhookPayloadValidationRequest,
    ) -> WebhookPayloadValidationResponse | None:
        source = self.get_source(source_id)
        if source is None:
            return None

        configuration = self.get_source_provider_configuration(source_id)
        if configuration is None:
            return None
        if configuration.provider_key != "webhook_future":
            raise ValueError("webhook_provider_required")

        warnings = [
            "Webhook authentication is not implemented; this validation is dry-run only."
        ]
        if payload.shared_secret_marker:
            warnings.append("shared_secret_marker was treated as a dry-run marker only.")

        if (
            "shared_secret_configured" in configuration.missing_fields
            or configuration.safe_config_preview.get("shared_secret_configured") != "configured"
        ):
            return _webhook_payload_validation_response(
                source_id=source_id,
                valid=False,
                candidate=None,
                skipped_reason="not_configured",
                warnings=warnings
                + [
                    "Configure shared_secret_configured metadata before webhook validation can run."
                ],
            )

        payload_data = dict(payload.payload)
        candidate_summary = classify_webhook_payload(payload_data)
        warnings.extend(candidate_summary.warnings)

        allowed_source_name = _webhook_config_value(configuration, "allowed_source_name")
        payload_source_name = _webhook_payload_string(payload_data.get("source_name"))
        if allowed_source_name:
            if payload_source_name and payload_source_name != allowed_source_name:
                candidate = _webhook_candidate_from_summary(
                    source_id=source_id,
                    stream_id=None,
                    zone_id=None,
                    summary=candidate_summary,
                )
                return _webhook_payload_validation_response(
                    source_id=source_id,
                    valid=False,
                    candidate=candidate,
                    skipped_reason="source_name_not_allowed",
                    warnings=warnings
                    + ["Payload source_name does not match the configured allowlist."],
                )
            if payload_source_name is None:
                warnings.append(
                    "Payload source_name is missing; configured allowed_source_name was not checked."
                )

        stream_id = (
            _webhook_payload_string(payload_data.get("stream_id"))
            or payload.default_stream_id
            or _webhook_config_value(configuration, "default_stream_id")
        )
        selected_stream_id: str | None = None
        if stream_id:
            stream = self.get_stream(stream_id)
            if stream is None:
                candidate = _webhook_candidate_from_summary(
                    source_id=source_id,
                    stream_id=stream_id,
                    zone_id=None,
                    summary=candidate_summary,
                )
                return _webhook_payload_validation_response(
                    source_id=source_id,
                    valid=False,
                    candidate=candidate,
                    skipped_reason="stream_not_found",
                    warnings=warnings + ["Webhook payload stream_id was not found."],
                )
            if stream.source_id != source_id:
                candidate = _webhook_candidate_from_summary(
                    source_id=source_id,
                    stream_id=stream_id,
                    zone_id=None,
                    summary=candidate_summary,
                )
                return _webhook_payload_validation_response(
                    source_id=source_id,
                    valid=False,
                    candidate=candidate,
                    skipped_reason="stream_source_mismatch",
                    warnings=warnings + ["Webhook payload stream_id does not belong to this Source."],
                )
            selected_stream_id = stream.id

        zone_id = (
            _webhook_payload_string(payload_data.get("zone_id"))
            or payload.default_zone_id
            or _webhook_config_value(configuration, "default_zone_id")
        )
        selected_zone_id: str | None = None
        if zone_id:
            zone = self.get_zone(zone_id)
            if zone is None:
                candidate = _webhook_candidate_from_summary(
                    source_id=source_id,
                    stream_id=selected_stream_id,
                    zone_id=zone_id,
                    summary=candidate_summary,
                )
                return _webhook_payload_validation_response(
                    source_id=source_id,
                    valid=False,
                    candidate=candidate,
                    skipped_reason="zone_not_found",
                    warnings=warnings + ["Webhook payload zone_id was not found."],
                )

            if selected_stream_id is None:
                zone_stream = self.get_stream(zone.stream_id)
                if zone_stream is None or zone_stream.source_id != source_id:
                    candidate = _webhook_candidate_from_summary(
                        source_id=source_id,
                        stream_id=zone.stream_id,
                        zone_id=zone.id,
                        summary=candidate_summary,
                    )
                    return _webhook_payload_validation_response(
                        source_id=source_id,
                        valid=False,
                        candidate=candidate,
                        skipped_reason="zone_source_mismatch",
                        warnings=warnings + ["Webhook payload zone_id does not belong to this Source."],
                    )
                selected_stream_id = zone_stream.id
            elif zone.stream_id != selected_stream_id:
                candidate = _webhook_candidate_from_summary(
                    source_id=source_id,
                    stream_id=selected_stream_id,
                    zone_id=zone.id,
                    summary=candidate_summary,
                )
                return _webhook_payload_validation_response(
                    source_id=source_id,
                    valid=False,
                    candidate=candidate,
                    skipped_reason="zone_stream_mismatch",
                    warnings=warnings + ["Webhook payload zone_id does not belong to the selected Stream."],
                )

            selected_zone_id = zone.id
            if zone.zone_type == ZoneType.privacy:
                candidate = _webhook_candidate_from_summary(
                    source_id=source_id,
                    stream_id=selected_stream_id,
                    zone_id=selected_zone_id,
                    summary=candidate_summary,
                )
                return _webhook_payload_validation_response(
                    source_id=source_id,
                    valid=False,
                    candidate=candidate,
                    skipped_reason="privacy_zone",
                    warnings=warnings + ["Webhook payload targets a privacy zone."],
                )
            if zone.zone_type == ZoneType.ignore:
                candidate = _webhook_candidate_from_summary(
                    source_id=source_id,
                    stream_id=selected_stream_id,
                    zone_id=selected_zone_id,
                    summary=candidate_summary,
                )
                return _webhook_payload_validation_response(
                    source_id=source_id,
                    valid=False,
                    candidate=candidate,
                    skipped_reason="ignore_zone",
                    warnings=warnings + ["Webhook payload targets an ignore zone."],
                )

        if selected_stream_id is None and candidate_summary.candidate_type != "heartbeat":
            warnings.append("No Stream context was supplied; candidate remains unanchored.")

        candidate = _webhook_candidate_from_summary(
            source_id=source_id,
            stream_id=selected_stream_id,
            zone_id=selected_zone_id,
            summary=candidate_summary,
        )
        return _webhook_payload_validation_response(
            source_id=source_id,
            valid=candidate_summary.valid,
            candidate=candidate,
            skipped_reason=candidate_summary.skipped_reason,
            warnings=warnings,
        )

    def list_streams(self) -> list[Stream]:
        with self.session_factory() as session:
            streams = session.scalars(select(StreamModel).order_by(StreamModel.id)).all()
            return [_stream_from_model(stream) for stream in streams]

    def get_stream(self, stream_id: str) -> Stream | None:
        with self.session_factory() as session:
            stream = session.get(StreamModel, stream_id)
            return _stream_from_model(stream) if stream else None

    def get_stream_playback_status(self, stream_id: str) -> StreamPlaybackStatus | None:
        with self.session_factory() as session:
            stream = session.get(StreamModel, stream_id)
            if stream is None:
                return None

            source = session.get(CameraSourceModel, stream.source_id)
            if source is None:
                return StreamPlaybackStatus(
                    stream_id=stream.id,
                    source_id=stream.source_id,
                    status=StreamPlaybackStatusValue.unavailable,
                    playback_kind=StreamPlaybackKind.placeholder,
                    display_title=stream.name,
                    message="The stream source is missing, so playback cannot be shown.",
                    setup_hint="Restore the source before connecting future playback adapters.",
                    supports_zone_editing=True,
                    supports_live_playback=False,
                )

            adapter_key = source.kind
            model = session.get(SourceProviderConfigurationModel, source.id)
            configured_provider_key = model.provider_key if model is not None else None
            if configured_provider_key == "folder_import_future":
                configuration = _source_provider_configuration_from_model(
                    source,
                    model,
                    [stream.id],
                )
                if configuration.missing_fields:
                    message = (
                        "This stream has folder/trail-cam provider metadata pending. "
                        "Playback remains placeholder/media-context only."
                    )
                    setup_hint = (
                        "Add folder path metadata before folder preview/import can run."
                    )
                else:
                    message = (
                        "Folder/trail-cam metadata is configured for future import context. "
                        "This stream does not provide live playback."
                    )
                    setup_hint = (
                        "Preview or import folder media from Source setup; imported media "
                        "remains MediaAsset context until a future evidence handoff."
                    )
                return StreamPlaybackStatus(
                    stream_id=stream.id,
                    source_id=stream.source_id,
                    status=StreamPlaybackStatusValue.not_configured,
                    playback_kind=StreamPlaybackKind.placeholder,
                    display_title=stream.name,
                    message=message,
                    setup_hint=setup_hint,
                    supports_zone_editing=True,
                    supports_live_playback=False,
                    adapter_key=configured_provider_key,
                )
            if configured_provider_key == "webhook_future":
                configuration = _source_provider_configuration_from_model(
                    source,
                    model,
                    [stream.id],
                )
                if configuration.missing_fields:
                    message = (
                        "This stream has webhook provider metadata pending. "
                        "Playback remains placeholder/media-context only."
                    )
                    setup_hint = (
                        "Add shared secret metadata before future webhook validation or "
                        "ingest can be implemented."
                    )
                else:
                    message = (
                        "Webhook metadata is configured for future ingest context. "
                        "This stream does not provide live playback."
                    )
                    setup_hint = (
                        "Webhook endpoint implementation is future work; no payloads "
                        "are accepted yet."
                    )
                return StreamPlaybackStatus(
                    stream_id=stream.id,
                    source_id=stream.source_id,
                    status=StreamPlaybackStatusValue.not_configured,
                    playback_kind=StreamPlaybackKind.placeholder,
                    display_title=stream.name,
                    message=message,
                    setup_hint=setup_hint,
                    supports_zone_editing=True,
                    supports_live_playback=False,
                    adapter_key=configured_provider_key,
                )

            if source.kind == SourceKind.demo.value:
                return StreamPlaybackStatus(
                    stream_id=stream.id,
                    source_id=stream.source_id,
                    status=StreamPlaybackStatusValue.demo,
                    playback_kind=StreamPlaybackKind.demo_panel,
                    display_title=stream.name,
                    message=(
                        "This stream uses the local demo panel; no real video playback "
                        "is connected yet."
                    ),
                    setup_hint=(
                        "Future source adapters will feed this contract while zone editing "
                        "continues to work here."
                    ),
                    supports_zone_editing=True,
                    supports_live_playback=False,
                    adapter_key=adapter_key,
                )

            if source.status == SourceStatus.disconnected.value:
                status = StreamPlaybackStatusValue.offline
                message = "The source is disconnected, so MockingBird can show only a placeholder."
                setup_hint = "Reconnect or configure a future source adapter to enable playback."
            elif source.status == SourceStatus.needs_setup.value:
                status = StreamPlaybackStatusValue.not_configured
                message = "This stream needs source setup before playback can be shown."
                setup_hint = "Complete source setup later; zones can still be prepared now."
            else:
                status = StreamPlaybackStatusValue.not_configured
                message = "This stream has product metadata but no playback adapter configured yet."
                setup_hint = (
                    "A future source adapter can feed playback here without changing review "
                    "or zone workflows."
                )

            return StreamPlaybackStatus(
                stream_id=stream.id,
                source_id=stream.source_id,
                status=status,
                playback_kind=StreamPlaybackKind.placeholder,
                display_title=stream.name,
                message=message,
                setup_hint=setup_hint,
                supports_zone_editing=True,
                supports_live_playback=False,
                adapter_key=adapter_key,
            )

    def streams_for_source(self, source_id: str) -> list[Stream]:
        with self.session_factory() as session:
            streams = session.scalars(
                select(StreamModel)
                .where(StreamModel.source_id == source_id)
                .order_by(StreamModel.id)
            ).all()
            return [_stream_from_model(stream) for stream in streams]

    def _stream_ids_for_source(self, session: Session, source_id: str) -> list[str]:
        return [
            stream.id
            for stream in session.scalars(
                select(StreamModel).where(StreamModel.source_id == source_id).order_by(StreamModel.id)
            ).all()
        ]

    def list_zones(self) -> list[Zone]:
        with self.session_factory() as session:
            zones = session.scalars(select(ZoneModel).order_by(ZoneModel.id)).all()
            return [_zone_from_model(zone) for zone in zones]

    def get_zone(self, zone_id: str) -> Zone | None:
        with self.session_factory() as session:
            zone = session.get(ZoneModel, zone_id)
            return _zone_from_model(zone) if zone else None

    def zones_for_stream(self, stream_id: str) -> list[Zone]:
        with self.session_factory() as session:
            return self._zones_for_stream(session, stream_id)

    def create_zone(self, payload: ZoneCreate) -> Zone:
        with self.session_factory() as session:
            with session.begin():
                zone = ZoneModel(
                    id=self._next_id(session, ZoneModel, "zone"),
                    stream_id=payload.stream_id,
                    name=payload.name,
                    zone_type=payload.zone_type.value,
                    polygon_json=_points_to_json(payload.polygon),
                    is_active=payload.is_active,
                )
                session.add(zone)
                session.flush()
                return _zone_from_model(zone)

    def update_zone(self, zone_id: str, payload: ZoneUpdate) -> Zone | None:
        with self.session_factory() as session:
            with session.begin():
                zone = session.get(ZoneModel, zone_id)
                if zone is None:
                    return None

                if payload.name is not None:
                    zone.name = payload.name
                if payload.zone_type is not None:
                    zone.zone_type = payload.zone_type.value
                if payload.polygon is not None:
                    zone.polygon_json = _points_to_json(payload.polygon)
                if payload.is_active is not None:
                    zone.is_active = payload.is_active

                session.flush()
                return _zone_from_model(zone)

    def list_events(self) -> list[Event]:
        with self.session_factory() as session:
            events = session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
            return [self._event_from_model(session, event) for event in events]

    def get_event(self, event_id: str) -> Event | None:
        with self.session_factory() as session:
            event = session.get(EventModel, event_id)
            return self._event_from_model(session, event) if event else None

    def events_for_stream(self, stream_id: str) -> list[Event]:
        with self.session_factory() as session:
            events = session.scalars(
                select(EventModel)
                .where(EventModel.stream_id == stream_id)
                .order_by(EventModel.started_at)
            ).all()
            return [self._event_from_model(session, event) for event in events]

    def list_visits(self) -> list[Visit]:
        with self.session_factory() as session:
            visits = session.scalars(select(VisitModel).order_by(VisitModel.id)).all()
            return [_visit_from_model(visit) for visit in visits]

    def get_visit(self, visit_id: str) -> Visit | None:
        with self.session_factory() as session:
            visit = session.get(VisitModel, visit_id)
            return _visit_from_model(visit) if visit else None

    def visits_for_event(self, event_id: str) -> list[Visit]:
        with self.session_factory() as session:
            return self._visits_for_event(session, event_id)

    def list_media_assets(self) -> list[MediaAsset]:
        with self.session_factory() as session:
            assets = session.scalars(
                select(MediaAssetModel).order_by(MediaAssetModel.created_at, MediaAssetModel.id)
            ).all()
            return [_media_asset_from_model(asset) for asset in assets]

    def get_media_asset(self, media_id: str) -> MediaAsset | None:
        with self.session_factory() as session:
            asset = session.get(MediaAssetModel, media_id)
            return _media_asset_from_model(asset) if asset else None

    def media_asset_for_path(self, media_path: str | None) -> MediaAsset | None:
        if media_path is None:
            return None

        with self.session_factory() as session:
            return self._media_asset_for_path_from_session(session, media_path)

    def media_file_path(self, media_id: str) -> Path | None:
        asset = self.get_media_asset(media_id)
        if asset is None:
            return None
        return Path(asset.local_path)

    def saved_preview_retention_report(self) -> SavedMediaRetentionReportResponse:
        with self.session_factory() as session:
            asset_models = session.scalars(
                select(MediaAssetModel).order_by(MediaAssetModel.created_at, MediaAssetModel.id)
            ).all()
            items = [
                self._saved_preview_retention_item(session, asset_model)
                for asset_model in asset_models
                if _is_external_url_preview_media_asset(asset_model)
            ]

        risk_counts = Counter(item.risk_level for item in items)
        summary_warnings: list[str] = []
        if any(item.warnings for item in items):
            summary_warnings.append(
                "Some saved preview media has retention warnings; inspect item warnings."
            )

        return SavedMediaRetentionReportResponse(
            items=items,
            summary=SavedMediaRetentionSummary(
                total_items=len(items),
                total_known_bytes=sum(item.size_bytes or 0 for item in items),
                unknown_size_count=sum(1 for item in items if item.size_bytes is None),
                low_risk_count=risk_counts["low"],
                medium_risk_count=risk_counts["medium"],
                high_risk_count=risk_counts["high"],
                protected_count=risk_counts["protected"],
                warnings=summary_warnings,
            ),
            generated_at=datetime.now(UTC),
            dry_run_only=True,
        )

    def saved_preview_cleanup_dry_run(
        self,
        payload: SavedMediaCleanupDryRunRequest,
    ) -> SavedMediaCleanupDryRunResponse:
        report = self.saved_preview_retention_report()
        report_ids = {item.media_asset_id for item in report.items}
        selected_ids = {
            media_id.strip()
            for media_id in payload.media_asset_ids or []
            if media_id.strip()
        }
        selected_risk_levels = {
            risk_level.strip().lower()
            for risk_level in payload.risk_levels or []
            if risk_level.strip()
        }
        if not selected_ids and not selected_risk_levels:
            selected_risk_levels = {"low"}

        valid_risk_levels = {"low", "medium", "high", "protected"}
        unsupported_risk_levels = selected_risk_levels - valid_risk_levels
        selected_risk_levels &= valid_risk_levels

        warnings = ["Dry-run only; no files or records were deleted."]
        for media_id in sorted(selected_ids - report_ids):
            warnings.append(
                f"MediaAsset {media_id} is not a saved external_url preview retention item."
            )
        for risk_level in sorted(unsupported_risk_levels):
            warnings.append(f"Unsupported retention risk level ignored: {risk_level}.")

        dry_run_items: list[SavedMediaCleanupDryRunItem] = []
        for item in report.items:
            if selected_ids and item.media_asset_id not in selected_ids:
                continue
            if selected_risk_levels and item.risk_level not in selected_risk_levels:
                continue

            dry_run_items.append(self._saved_preview_cleanup_dry_run_item(item, payload))

        return SavedMediaCleanupDryRunResponse(
            items=dry_run_items,
            total_would_delete_files=sum(1 for item in dry_run_items if item.would_delete_file),
            total_would_delete_records=sum(
                1 for item in dry_run_items if item.would_delete_record
            ),
            total_known_bytes_to_delete=sum(
                item.size_bytes or 0 for item in dry_run_items if item.would_delete_file
            ),
            skipped_count=sum(1 for item in dry_run_items if item.would_skip),
            protected_skipped_count=sum(
                1
                for item in dry_run_items
                if item.skip_reason == "protected_media_skipped"
            ),
            dry_run=True,
            creates_truth=False,
            deletes_truth=False,
            warnings=warnings,
        )

    def _saved_preview_retention_item(
        self,
        session: Session,
        asset_model: MediaAssetModel,
    ) -> SavedMediaRetentionItem:
        note_fields = _external_url_preview_note_fields(asset_model.notes)
        warnings: list[str] = []
        fetched_at = _parsed_note_datetime(note_fields.get("fetched_at"), warnings)
        size_bytes, size_warnings = self._saved_preview_size_bytes(asset_model)
        warnings.extend(size_warnings)

        motion_evidence = session.scalars(
            select(MotionEvidenceModel)
            .where(MotionEvidenceModel.snapshot_media_asset_id == asset_model.id)
            .order_by(MotionEvidenceModel.created_at, MotionEvidenceModel.id)
        ).all()
        linked_event_ids = {
            evidence.promoted_event_id
            for evidence in motion_evidence
            if evidence.promoted_event_id is not None
        }
        linked_visit_ids = {
            evidence.promoted_visit_id
            for evidence in motion_evidence
            if evidence.promoted_visit_id is not None
        }

        visit_models_by_id: dict[str, VisitModel] = {}
        if asset_model.local_path:
            for visit_model in session.scalars(
                select(VisitModel).where(
                    VisitModel.representative_media_path == asset_model.local_path
                )
            ).all():
                linked_visit_ids.add(visit_model.id)
                linked_event_ids.add(visit_model.event_id)
                visit_models_by_id[visit_model.id] = visit_model

        for visit_id in linked_visit_ids:
            if visit_id not in visit_models_by_id:
                visit_model = session.get(VisitModel, visit_id)
                if visit_model is not None:
                    visit_models_by_id[visit_id] = visit_model
                else:
                    warnings.append(
                        f"Linked Visit {visit_id} was not found; classified conservatively."
                    )

        event_models_by_id: dict[str, EventModel] = {}
        for event_id in linked_event_ids:
            event_model = session.get(EventModel, event_id)
            if event_model is not None:
                event_models_by_id[event_id] = event_model
            else:
                warnings.append(
                    f"Linked Event {event_id} was not found; classified conservatively."
                )

        reviewed_truth_refs: set[str] = set()
        for visit_id, visit_model in visit_models_by_id.items():
            if (
                visit_model.review_status == ReviewStatus.reviewed.value
                or visit_model.reviewed_label is not None
            ):
                reviewed_truth_refs.add(f"visit:{visit_id}")
            for label_model in self._review_label_models_for_visit(session, visit_id):
                reviewed_truth_refs.add(f"review-label:{label_model.id}")

        for event_id, event_model in event_models_by_id.items():
            if event_model.review_status == ReviewStatus.reviewed.value:
                reviewed_truth_refs.add(f"event:{event_id}")
            for label_model in self._review_label_models_for_event(session, event_id):
                reviewed_truth_refs.add(f"review-label:{label_model.id}")

        pending_count = sum(
            1
            for evidence in motion_evidence
            if evidence.status == MotionEvidenceStatus.pending.value
        )
        ignored_count = sum(
            1
            for evidence in motion_evidence
            if evidence.status == MotionEvidenceStatus.ignored.value
        )
        promoted_count = sum(
            1
            for evidence in motion_evidence
            if evidence.status == MotionEvidenceStatus.promoted.value
        )
        known_statuses = {
            MotionEvidenceStatus.pending.value,
            MotionEvidenceStatus.ignored.value,
            MotionEvidenceStatus.promoted.value,
        }
        if any(evidence.status not in known_statuses for evidence in motion_evidence):
            warnings.append(
                "Unknown MotionEvidence status encountered; classified conservatively."
            )

        reviewed_truth_count = len(reviewed_truth_refs)
        if reviewed_truth_count > 0:
            media_state = "reviewed_truth_context"
            risk_level = "protected"
            recommended_action = "Skip by default; media is linked to reviewed truth."
        elif linked_event_ids or linked_visit_ids:
            media_state = "linked_event_visit"
            risk_level = "high"
            recommended_action = "Keep by default; media supports Event/Visit review context."
        elif promoted_count > 0:
            media_state = "linked_promoted_evidence"
            risk_level = "high"
            recommended_action = "Keep by default; media is linked to promoted evidence."
        elif pending_count > 0:
            media_state = "linked_pending_evidence"
            risk_level = "medium"
            recommended_action = "Review pending MotionEvidence before cleanup."
        elif ignored_count > 0:
            media_state = "linked_ignored_evidence"
            risk_level = "medium"
            recommended_action = "Review ignored MotionEvidence before cleanup."
        elif not motion_evidence:
            media_state = "saved_unlinked"
            risk_level = "low"
            recommended_action = "Eligible for future low-risk cleanup dry run."
        else:
            media_state = "unknown"
            risk_level = "high"
            recommended_action = "Inspect manually before cleanup."
            warnings.append("Insufficient linkage metadata; classified as high risk.")

        return SavedMediaRetentionItem(
            media_asset_id=asset_model.id,
            source_id=asset_model.source_id,
            stream_id=asset_model.stream_id,
            file_name=asset_model.filename,
            content_type=asset_model.content_type,
            size_bytes=size_bytes,
            created_at=_as_utc(asset_model.created_at),
            fetched_at=fetched_at,
            provider_key=note_fields.get("provider_key"),
            provenance=_saved_preview_provenance(note_fields),
            linked_motion_evidence_count=len(motion_evidence),
            linked_event_count=len(linked_event_ids),
            linked_visit_count=len(linked_visit_ids),
            reviewed_truth_count=reviewed_truth_count,
            risk_level=risk_level,
            media_state=media_state,
            recommended_action=recommended_action,
            warnings=warnings,
        )

    def _saved_preview_size_bytes(
        self,
        asset_model: MediaAssetModel,
    ) -> tuple[int | None, list[str]]:
        warnings: list[str] = []
        size_bytes = asset_model.file_size_bytes if asset_model.file_size_bytes >= 0 else None
        media_root = self.media_root.resolve()
        try:
            media_path = Path(asset_model.local_path).resolve()
        except OSError:
            warnings.append("Local media path could not be resolved; filesystem metadata skipped.")
            return size_bytes, warnings

        if not media_path.is_relative_to(media_root):
            warnings.append(
                "Local media path is outside the configured media root; filesystem metadata skipped."
            )
            return size_bytes, warnings

        if not media_path.exists():
            warnings.append("Local media file is missing or stale; no file was opened.")
            return size_bytes, warnings

        if size_bytes is None:
            try:
                size_bytes = media_path.stat().st_size
            except OSError:
                warnings.append("Local media size could not be read from filesystem metadata.")
        return size_bytes, warnings

    def _saved_preview_cleanup_dry_run_item(
        self,
        item: SavedMediaRetentionItem,
        payload: SavedMediaCleanupDryRunRequest,
    ) -> SavedMediaCleanupDryRunItem:
        warnings = list(item.warnings)
        skip_reason: str | None = None
        mode = payload.mode.strip() if payload.mode.strip() else "delete_file_only"

        if item.risk_level == "protected" and not payload.include_protected:
            skip_reason = "protected_media_skipped"
        elif any("outside the configured media root" in warning for warning in warnings):
            skip_reason = "unsafe_media_path"
        elif any("missing or stale" in warning for warning in warnings):
            skip_reason = "stale_media_reference"
        elif mode not in {"delete_file_only", "delete_media_asset", "archive"}:
            skip_reason = "unsupported_mode"
            warnings.append(f"Unsupported cleanup mode ignored: {mode}.")

        would_skip = skip_reason is not None
        would_delete_file = False
        would_delete_record = False
        if not would_skip:
            if mode == "delete_file_only":
                would_delete_file = True
            elif mode == "delete_media_asset":
                would_delete_file = True
                would_delete_record = True

        return SavedMediaCleanupDryRunItem(
            media_asset_id=item.media_asset_id,
            risk_level=item.risk_level,
            would_delete_file=would_delete_file,
            would_delete_record=would_delete_record,
            would_skip=would_skip,
            skip_reason=skip_reason,
            file_name=item.file_name,
            size_bytes=item.size_bytes,
            warnings=warnings,
        )

    def cleanup_saved_preview_media(
        self,
        media_asset_id: str,
        payload: SavedMediaCleanupRequest,
    ) -> SavedMediaCleanupResponse | None:
        media_id = media_asset_id.strip()
        if not media_id:
            return None

        mode = payload.mode.strip() if payload.mode.strip() else "delete_file_only"
        if not payload.confirm:
            raise ValueError("cleanup_requires_confirmation")
        if mode != "delete_file_only":
            raise ValueError("unsupported_cleanup_mode")

        with self.session_factory() as session:
            asset_model = session.get(MediaAssetModel, media_id)
            if asset_model is None:
                return None

            if not _is_external_url_preview_media_asset(asset_model):
                return SavedMediaCleanupResponse(
                    media_asset_id=media_id,
                    status="rejected",
                    risk_level="unknown",
                    media_state="unknown",
                    file_deleted=False,
                    record_deleted=False,
                    creates_truth=False,
                    deletes_truth=False,
                    message=(
                        "Only saved external_url preview MediaAssets are eligible for "
                        "file-only cleanup in this phase."
                    ),
                    file_name=asset_model.filename,
                    size_bytes=asset_model.file_size_bytes,
                    warnings=["MediaAsset is not a saved external_url preview."],
                )

            item = self._saved_preview_retention_item(session, asset_model)
            local_path = asset_model.local_path

        warnings = list(item.warnings)
        if item.risk_level != "low" or item.media_state != "saved_unlinked":
            warnings.append(
                "Phase 12F cleanup is limited to low-risk unlinked saved preview media."
            )
            return SavedMediaCleanupResponse(
                media_asset_id=item.media_asset_id,
                status="rejected",
                risk_level=item.risk_level,
                media_state=item.media_state,
                file_deleted=False,
                record_deleted=False,
                creates_truth=False,
                deletes_truth=False,
                message=(
                    "Cleanup rejected. This MediaAsset is linked to evidence, "
                    "Event/Visit context, reviewed truth, or unknown retention state."
                ),
                file_name=item.file_name,
                size_bytes=item.size_bytes,
                warnings=warnings,
            )

        media_path, rejection_reason, path_warnings = self._safe_saved_preview_cleanup_path(
            local_path,
        )
        warnings.extend(path_warnings)
        if rejection_reason is not None or media_path is None:
            return SavedMediaCleanupResponse(
                media_asset_id=item.media_asset_id,
                status="rejected",
                risk_level=item.risk_level,
                media_state=item.media_state,
                file_deleted=False,
                record_deleted=False,
                creates_truth=False,
                deletes_truth=False,
                message=rejection_reason or "Cleanup rejected by path safety checks.",
                file_name=item.file_name,
                size_bytes=item.size_bytes,
                warnings=warnings,
            )

        if not media_path.exists():
            return SavedMediaCleanupResponse(
                media_asset_id=item.media_asset_id,
                status="already_missing",
                risk_level=item.risk_level,
                media_state=item.media_state,
                file_deleted=False,
                record_deleted=False,
                creates_truth=False,
                deletes_truth=False,
                message=(
                    "Local file was already missing. The MediaAsset record remains and "
                    "no truth was changed."
                ),
                file_name=item.file_name,
                size_bytes=item.size_bytes,
                warnings=warnings,
            )

        try:
            media_path.unlink()
        except OSError:
            warnings.append("Local file could not be deleted; no records were changed.")
            return SavedMediaCleanupResponse(
                media_asset_id=item.media_asset_id,
                status="rejected",
                risk_level=item.risk_level,
                media_state=item.media_state,
                file_deleted=False,
                record_deleted=False,
                creates_truth=False,
                deletes_truth=False,
                message="File-only cleanup failed before deleting the local file.",
                file_name=item.file_name,
                size_bytes=item.size_bytes,
                warnings=warnings,
            )

        return SavedMediaCleanupResponse(
            media_asset_id=item.media_asset_id,
            status="deleted_file",
            risk_level=item.risk_level,
            media_state=item.media_state,
            file_deleted=True,
            record_deleted=False,
            creates_truth=False,
            deletes_truth=False,
            message=(
                "Deleted the local saved preview file only. The MediaAsset record, "
                "evidence, Events, Visits, labels, exports, and truth remain unchanged."
            ),
            file_name=item.file_name,
            size_bytes=item.size_bytes,
            warnings=warnings,
        )

    def _safe_saved_preview_cleanup_path(
        self,
        local_path: str,
    ) -> tuple[Path | None, str | None, list[str]]:
        warnings: list[str] = []
        try:
            media_root = self.media_root.resolve()
            candidate = Path(local_path)
            if not candidate.is_absolute():
                candidate = self.media_root / candidate
            candidate = candidate.absolute()
            resolved_candidate = candidate.resolve(strict=False)
        except OSError:
            return (
                None,
                "Cleanup rejected because the local media path could not be resolved.",
                ["Local media path could not be resolved."],
            )

        if not resolved_candidate.is_relative_to(media_root):
            return (
                None,
                "Cleanup rejected because the local media path is outside the media root.",
                ["Local media path is outside the configured media root."],
            )

        for path_part in (candidate, *candidate.parents):
            if path_part == media_root:
                break
            if path_part.is_symlink():
                return (
                    None,
                    "Cleanup rejected because symlink media paths are not eligible.",
                    ["Local media path includes a symlink; file-only cleanup skipped."],
                )

        if candidate.exists() and candidate.is_dir():
            return (
                None,
                "Cleanup rejected because the local media path is a directory.",
                ["Local media path points to a directory; file-only cleanup skipped."],
            )

        if candidate.exists() and not candidate.is_file():
            return (
                None,
                "Cleanup rejected because the local media path is not a regular file.",
                ["Local media path is not a regular file; file-only cleanup skipped."],
            )

        return candidate, None, warnings

    def create_external_url_preview_media_asset(
        self,
        *,
        source_id: str,
        stream_id: str,
        content: bytes,
        content_type: str,
        fetched_at: datetime,
        url_host: str | None = None,
        note: str | None = None,
    ) -> MediaAsset:
        if not content:
            raise ValueError("empty_file")

        media_type = SUPPORTED_MEDIA_CONTENT_TYPES.get(content_type)
        extension = EXTERNAL_URL_PREVIEW_EXTENSIONS.get(content_type)
        if media_type != "image" or extension is None:
            raise ValueError("unsupported_content_type")

        with self.session_factory() as session:
            with session.begin():
                source_model = session.get(CameraSourceModel, source_id)
                if source_model is None:
                    raise ValueError("missing_source")

                stream_model = session.get(StreamModel, stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")
                if stream_model.source_id != source_id:
                    raise ValueError("stream_source_mismatch")

                media_id = self._next_id(session, MediaAssetModel, "media-asset")
                original_filename = f"external-url-preview-{media_id}{extension}"
                filename = f"{media_id}-external-url-preview{extension}"
                filename, local_path = self._write_media_file(filename, content)
                notes = self._external_url_preview_media_notes(
                    source_id=source_id,
                    stream_id=stream_id,
                    fetched_at=fetched_at,
                    content_type=content_type,
                    bytes_written=len(content),
                    url_host=url_host,
                    note=note,
                )
                asset_model = MediaAssetModel(
                    id=media_id,
                    source_id=source_id,
                    stream_id=stream_id,
                    filename=filename,
                    content_type=content_type,
                    media_type=media_type,
                    local_path=str(local_path),
                    original_filename=original_filename,
                    file_size_bytes=len(content),
                    created_at=fetched_at,
                    notes=notes,
                )
                session.add(asset_model)
                session.flush()
                return _media_asset_from_model(asset_model)

    def create_motion_evidence_from_saved_media(
        self,
        media_asset_id: str,
        payload: SavedPreviewMotionEvidenceRequest,
    ) -> _SavedMediaMotionEvidenceResult:
        media_id = media_asset_id.strip()
        if not media_id:
            raise ValueError("missing_media_asset")
        duplicate_policy = _clean_optional_text(payload.duplicate_policy) or "skip_existing"
        if duplicate_policy not in {"skip_existing", "allow_duplicate"}:
            raise ValueError("unsupported_duplicate_policy")

        with self.session_factory() as session:
            with session.begin():
                asset_model = session.get(MediaAssetModel, media_id)
                if asset_model is None:
                    raise ValueError("missing_media_asset")
                if (
                    asset_model.media_type != "image"
                    or asset_model.content_type not in EXTERNAL_URL_PREVIEW_EXTENSIONS
                ):
                    raise ValueError("unsupported_motion_evidence_media_type")
                if not Path(asset_model.local_path).is_file():
                    raise ValueError("missing_media_file")

                stream_id = _clean_optional_text(payload.stream_id) or asset_model.stream_id
                stream_model = session.get(StreamModel, stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")
                if asset_model.stream_id != stream_model.id:
                    raise ValueError("media_stream_mismatch")

                source_id = asset_model.source_id or stream_model.source_id
                source_model = session.get(CameraSourceModel, source_id)
                if source_model is None:
                    raise ValueError("missing_source")
                if stream_model.source_id != source_id:
                    raise ValueError("stream_source_mismatch")

                provenance_kind = _media_asset_motion_evidence_provenance_kind(asset_model)
                warnings: list[str] = []
                zone_id = _clean_optional_text(payload.zone_id)
                if zone_id is not None:
                    zone_model = session.get(ZoneModel, zone_id)
                    if zone_model is None:
                        raise ValueError("missing_zone")
                    if zone_model.stream_id != stream_model.id:
                        raise ValueError("zone_stream_mismatch")
                    if zone_model.zone_type in {
                        ZoneType.privacy.value,
                        ZoneType.ignore.value,
                    }:
                        raise ValueError("motion_evidence_creation_zone_blocked")
                else:
                    zone_model = next(
                        (
                            zone
                            for zone in session.scalars(
                                select(ZoneModel)
                                .where(
                                    ZoneModel.stream_id == stream_model.id,
                                    ZoneModel.is_active.is_(True),
                                )
                                .order_by(ZoneModel.id)
                            ).all()
                            if zone.zone_type
                            not in {
                                ZoneType.privacy.value,
                                ZoneType.ignore.value,
                            }
                        ),
                        None,
                    )
                    if zone_model is None:
                        raise ValueError("missing_reviewable_zone")
                    warnings.append(
                        "No zone was supplied; MockingBird used the first active "
                        "reviewable zone for this stream."
                    )

                existing_evidence = session.scalars(
                    select(MotionEvidenceModel)
                    .where(
                        MotionEvidenceModel.snapshot_media_asset_id == media_id,
                        MotionEvidenceModel.status.in_(
                            [
                                MotionEvidenceStatus.pending.value,
                                MotionEvidenceStatus.promoted.value,
                                MotionEvidenceStatus.ignored.value,
                            ]
                        ),
                    )
                    .order_by(MotionEvidenceModel.created_at, MotionEvidenceModel.id)
                ).first()
                if existing_evidence is not None and duplicate_policy == "skip_existing":
                    warnings.append(
                        "Existing MotionEvidence already references this MediaAsset; "
                        "no duplicate pending evidence was created."
                    )
                    return _SavedMediaMotionEvidenceResult(
                        evidence=_motion_evidence_from_model(existing_evidence),
                        warnings=warnings,
                        duplicate_skipped=True,
                        existing_motion_evidence_id=existing_evidence.id,
                        provenance_kind=provenance_kind,
                    )

                scoring_source = {
                    "external_url_preview": "saved_preview_media_asset",
                    "folder_import": "folder_import_media_asset",
                }.get(provenance_kind, "media_asset")
                source_label = {
                    "external_url_preview": "saved MediaAsset",
                    "folder_import": "folder-imported MediaAsset",
                }.get(provenance_kind, "MediaAsset")
                note_parts = [
                    f"Created from {source_label} {media_id} by explicit user action.",
                    "No Events, Visits, ReviewLabels, or truth were created.",
                ]
                reason = _clean_optional_text(payload.reason)
                if reason is not None:
                    note_parts.append(f"Reason: {reason}")
                note = _clean_optional_text(payload.note)
                if note is not None:
                    note_parts.append(f"Note: {note}")

                evidence_model = MotionEvidenceModel(
                    id=self._next_id(session, MotionEvidenceModel, "motion-evidence"),
                    source_id=source_id,
                    stream_id=stream_model.id,
                    zone_id=zone_model.id,
                    start_frame_index=None,
                    end_frame_index=None,
                    best_frame_index=None,
                    start_time=None,
                    end_time=None,
                    best_frame_time=None,
                    peak_changed_ratio=0.0,
                    triggered_frame_count=1,
                    scoring_config_json=json.dumps(
                        {
                            "source": scoring_source,
                            "media_asset_id": media_id,
                            "motion_score_available": False,
                            "requires_review": True,
                        },
                        sort_keys=True,
                    ),
                    snapshot_media_asset_id=media_id,
                    status=MotionEvidenceStatus.pending.value,
                    promoted_event_id=None,
                    promoted_visit_id=None,
                    created_at=datetime.now(UTC),
                    notes="\n".join(note_parts),
                )
                session.add(evidence_model)
                session.flush()
                return _SavedMediaMotionEvidenceResult(
                    evidence=_motion_evidence_from_model(evidence_model),
                    warnings=warnings,
                    provenance_kind=provenance_kind,
                )

    def dry_run_folder_import_evidence_batch(
        self,
        payload: FolderImportEvidenceBatchDryRunRequest,
    ) -> FolderImportEvidenceBatchDryRunResponse:
        media_asset_ids = [
            media_asset_id.strip()
            for media_asset_id in (payload.media_asset_ids or [])
            if media_asset_id and media_asset_id.strip()
        ]
        source_id = _clean_optional_text(payload.source_id)
        stream_id = _clean_optional_text(payload.stream_id)
        zone_id = _clean_optional_text(payload.zone_id)
        duplicate_policy = _clean_optional_text(payload.duplicate_policy) or "skip_existing"
        if duplicate_policy not in {"skip_existing", "allow_duplicate"}:
            raise ValueError("unsupported_duplicate_policy")
        if not media_asset_ids and source_id is None and stream_id is None:
            raise ValueError("batch_dry_run_requires_selection")

        max_items = payload.max_items or 100
        warnings: list[str] = []
        if max_items > 500:
            max_items = 500
            warnings.append("max_items was capped at 500.")

        items: list[FolderImportEvidenceBatchDryRunItem] = []
        with self.session_factory() as session:
            if source_id is not None and session.get(CameraSourceModel, source_id) is None:
                raise ValueError("missing_source")
            if stream_id is not None:
                stream_model = session.get(StreamModel, stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")
                if source_id is not None and stream_model.source_id != source_id:
                    raise ValueError("stream_source_mismatch")

            if media_asset_ids:
                evaluation_ids = media_asset_ids[:max_items]
                overflow_ids = media_asset_ids[max_items:]
                if overflow_ids:
                    warnings.append(f"Dry run truncated at {max_items} items.")

                for media_asset_id in evaluation_ids:
                    items.append(
                        self._folder_import_evidence_batch_dry_run_item(
                            session,
                            media_asset_id=media_asset_id,
                            asset_model=session.get(MediaAssetModel, media_asset_id),
                            requested_source_id=source_id,
                            requested_stream_id=stream_id,
                            requested_zone_id=zone_id,
                            duplicate_policy=duplicate_policy,
                        )
                    )
                for media_asset_id in overflow_ids:
                    items.append(
                        FolderImportEvidenceBatchDryRunItem(
                            media_asset_id=media_asset_id,
                            eligible=False,
                            would_create_motion_evidence=False,
                            skip_reason="max_items_exceeded",
                            warnings=["Dry run max_items limit skipped this MediaAsset."],
                        )
                    )
            else:
                query = select(MediaAssetModel).order_by(
                    MediaAssetModel.created_at,
                    MediaAssetModel.id,
                )
                if source_id is not None:
                    query = query.where(MediaAssetModel.source_id == source_id)
                if stream_id is not None:
                    query = query.where(MediaAssetModel.stream_id == stream_id)

                folder_assets = [
                    asset_model
                    for asset_model in session.scalars(query).all()
                    if _is_folder_import_media_asset(asset_model)
                ]
                if len(folder_assets) > max_items:
                    warnings.append(f"Dry run truncated at {max_items} items.")
                for asset_model in folder_assets[:max_items]:
                    items.append(
                        self._folder_import_evidence_batch_dry_run_item(
                            session,
                            media_asset_id=asset_model.id,
                            asset_model=asset_model,
                            requested_source_id=source_id,
                            requested_stream_id=stream_id,
                            requested_zone_id=zone_id,
                            duplicate_policy=duplicate_policy,
                        )
                    )

        eligible_count = sum(1 for item in items if item.eligible)
        would_create_count = sum(1 for item in items if item.would_create_motion_evidence)
        duplicate_skipped_count = sum(1 for item in items if item.duplicate_skipped)
        return FolderImportEvidenceBatchDryRunResponse(
            items=items,
            total_items=len(items),
            eligible_count=eligible_count,
            would_create_count=would_create_count,
            duplicate_skipped_count=duplicate_skipped_count,
            skipped_count=len(items) - would_create_count,
            dry_run=True,
            creates_motion_evidence=False,
            creates_events=False,
            creates_visits=False,
            creates_truth=False,
            warnings=warnings,
        )

    def create_folder_import_evidence_batch(
        self,
        payload: FolderImportEvidenceBatchCreateRequest,
    ) -> FolderImportEvidenceBatchCreateResponse:
        if not payload.confirm:
            raise ValueError("batch_create_requires_confirmation")

        duplicate_policy = _clean_optional_text(payload.duplicate_policy) or "skip_existing"
        if duplicate_policy not in {"skip_existing", "allow_duplicate"}:
            raise ValueError("unsupported_duplicate_policy")

        dry_run = self.dry_run_folder_import_evidence_batch(
            FolderImportEvidenceBatchDryRunRequest(
                media_asset_ids=payload.media_asset_ids,
                source_id=payload.source_id,
                stream_id=payload.stream_id,
                zone_id=payload.zone_id,
                duplicate_policy=duplicate_policy,
                max_items=payload.max_items,
            )
        )

        items: list[FolderImportEvidenceBatchCreateItem] = []
        for dry_run_item in dry_run.items:
            if not dry_run_item.would_create_motion_evidence:
                items.append(
                    FolderImportEvidenceBatchCreateItem(
                        media_asset_id=dry_run_item.media_asset_id,
                        motion_evidence_id=None,
                        source_id=dry_run_item.source_id,
                        stream_id=dry_run_item.stream_id,
                        zone_id=dry_run_item.zone_id,
                        created=False,
                        duplicate_skipped=dry_run_item.duplicate_skipped,
                        existing_motion_evidence_id=dry_run_item.existing_motion_evidence_id,
                        skip_reason=dry_run_item.skip_reason,
                        warnings=dry_run_item.warnings,
                    )
                )
                continue

            result = self.create_motion_evidence_from_saved_media(
                dry_run_item.media_asset_id,
                SavedPreviewMotionEvidenceRequest(
                    stream_id=dry_run_item.stream_id,
                    zone_id=dry_run_item.zone_id,
                    note=payload.note,
                    reason=payload.reason,
                    duplicate_policy=duplicate_policy,
                ),
            )
            warnings = _unique_strings([*dry_run_item.warnings, *result.warnings])
            items.append(
                FolderImportEvidenceBatchCreateItem(
                    media_asset_id=dry_run_item.media_asset_id,
                    motion_evidence_id=(
                        None if result.duplicate_skipped else result.evidence.id
                    ),
                    source_id=result.evidence.source_id,
                    stream_id=result.evidence.stream_id,
                    zone_id=result.evidence.zone_id,
                    created=not result.duplicate_skipped,
                    duplicate_skipped=result.duplicate_skipped,
                    existing_motion_evidence_id=result.existing_motion_evidence_id,
                    skip_reason="duplicate_evidence" if result.duplicate_skipped else None,
                    warnings=warnings,
                )
            )

        created_count = sum(1 for item in items if item.created)
        duplicate_skipped_count = sum(1 for item in items if item.duplicate_skipped)
        return FolderImportEvidenceBatchCreateResponse(
            items=items,
            total_items=len(items),
            created_count=created_count,
            skipped_count=len(items) - created_count,
            duplicate_skipped_count=duplicate_skipped_count,
            creates_motion_evidence=created_count > 0,
            creates_events=False,
            creates_visits=False,
            creates_truth=False,
            message=(
                "Created pending MotionEvidence from eligible folder-imported media. "
                "No Events, Visits, labels, or truth were created."
                if created_count > 0
                else (
                    "No pending MotionEvidence was created. "
                    "No Events, Visits, labels, or truth were created."
                )
            ),
            warnings=dry_run.warnings,
        )

    def _folder_import_evidence_batch_dry_run_item(
        self,
        session: Session,
        *,
        media_asset_id: str,
        asset_model: MediaAssetModel | None,
        requested_source_id: str | None,
        requested_stream_id: str | None,
        requested_zone_id: str | None,
        duplicate_policy: str,
    ) -> FolderImportEvidenceBatchDryRunItem:
        source_id = asset_model.source_id if asset_model else requested_source_id
        stream_id = asset_model.stream_id if asset_model else requested_stream_id
        file_name = (
            asset_model.original_filename or asset_model.filename
            if asset_model is not None
            else None
        )

        def skipped(
            skip_reason: str,
            *,
            item_source_id: str | None = source_id,
            item_stream_id: str | None = stream_id,
            item_zone_id: str | None = requested_zone_id,
            item_warnings: list[str] | None = None,
            duplicate_skipped: bool = False,
            existing_motion_evidence_id: str | None = None,
        ) -> FolderImportEvidenceBatchDryRunItem:
            return FolderImportEvidenceBatchDryRunItem(
                media_asset_id=media_asset_id,
                source_id=item_source_id,
                stream_id=item_stream_id,
                zone_id=item_zone_id,
                file_name=file_name,
                eligible=False,
                would_create_motion_evidence=False,
                duplicate_skipped=duplicate_skipped,
                existing_motion_evidence_id=existing_motion_evidence_id,
                skip_reason=skip_reason,
                warnings=item_warnings or [],
            )

        if asset_model is None:
            return skipped(
                "unknown_media_asset",
                item_source_id=None,
                item_stream_id=None,
                item_zone_id=None,
                item_warnings=["MediaAsset was not found."],
            )
        if not _is_folder_import_media_asset(asset_model):
            return skipped(
                "not_folder_import_media",
                item_warnings=["MediaAsset was not created by folder import."],
            )
        if (
            asset_model.media_type != "image"
            or asset_model.content_type not in EXTERNAL_URL_PREVIEW_EXTENSIONS
        ):
            return skipped(
                "unsupported_media_type",
                item_warnings=["Only folder-imported still-image MediaAssets are eligible."],
            )
        if not Path(asset_model.local_path).is_file():
            return skipped(
                "missing_local_file",
                item_warnings=["Local media file was not found."],
            )

        stream_id = requested_stream_id or asset_model.stream_id
        if stream_id is None:
            return skipped("missing_stream_context", item_stream_id=None)
        stream_model = session.get(StreamModel, stream_id)
        if stream_model is None:
            return skipped("missing_stream_context", item_stream_id=stream_id)
        if asset_model.stream_id != stream_model.id:
            return skipped("stream_source_mismatch", item_stream_id=stream_model.id)

        source_id = asset_model.source_id or stream_model.source_id
        if requested_source_id is not None and source_id != requested_source_id:
            return skipped("stream_source_mismatch", item_source_id=source_id)
        if stream_model.source_id != source_id:
            return skipped("stream_source_mismatch", item_source_id=source_id)

        warnings: list[str] = []
        if requested_zone_id is not None:
            zone_model = session.get(ZoneModel, requested_zone_id)
            if zone_model is None or zone_model.stream_id != stream_model.id:
                return skipped(
                    "invalid_zone",
                    item_source_id=source_id,
                    item_stream_id=stream_model.id,
                    item_zone_id=requested_zone_id,
                )
            if zone_model.zone_type == ZoneType.privacy.value:
                return skipped(
                    "privacy_zone",
                    item_source_id=source_id,
                    item_stream_id=stream_model.id,
                    item_zone_id=zone_model.id,
                )
            if zone_model.zone_type == ZoneType.ignore.value:
                return skipped(
                    "ignore_zone",
                    item_source_id=source_id,
                    item_stream_id=stream_model.id,
                    item_zone_id=zone_model.id,
                )
        else:
            zone_model = next(
                (
                    zone
                    for zone in session.scalars(
                        select(ZoneModel)
                        .where(
                            ZoneModel.stream_id == stream_model.id,
                            ZoneModel.is_active.is_(True),
                        )
                        .order_by(ZoneModel.id)
                    ).all()
                    if zone.zone_type
                    not in {
                        ZoneType.privacy.value,
                        ZoneType.ignore.value,
                    }
                ),
                None,
            )
            if zone_model is None:
                return skipped(
                    "insufficient_context",
                    item_source_id=source_id,
                    item_stream_id=stream_model.id,
                    item_zone_id=None,
                )
            warnings.append(
                "No zone was supplied; MockingBird used the first active "
                "reviewable zone for this stream."
            )

        existing_evidence = session.scalars(
            select(MotionEvidenceModel)
            .where(
                MotionEvidenceModel.snapshot_media_asset_id == media_asset_id,
                MotionEvidenceModel.status.in_(
                    [
                        MotionEvidenceStatus.pending.value,
                        MotionEvidenceStatus.promoted.value,
                        MotionEvidenceStatus.ignored.value,
                    ]
                ),
            )
            .order_by(MotionEvidenceModel.created_at, MotionEvidenceModel.id)
        ).first()
        if existing_evidence is not None:
            if duplicate_policy == "skip_existing":
                return skipped(
                    "duplicate_evidence",
                    item_source_id=source_id,
                    item_stream_id=stream_model.id,
                    item_zone_id=zone_model.id,
                    item_warnings=[
                        "Existing MotionEvidence already references this MediaAsset; "
                        "no duplicate pending evidence would be created."
                    ],
                    duplicate_skipped=True,
                    existing_motion_evidence_id=existing_evidence.id,
                )
            warnings.append(
                "Existing MotionEvidence already references this MediaAsset; "
                "duplicate creation would be allowed by policy."
            )

        return FolderImportEvidenceBatchDryRunItem(
            media_asset_id=media_asset_id,
            source_id=source_id,
            stream_id=stream_model.id,
            zone_id=zone_model.id,
            file_name=file_name,
            eligible=True,
            would_create_motion_evidence=True,
            duplicate_skipped=False,
            existing_motion_evidence_id=(
                existing_evidence.id if existing_evidence is not None else None
            ),
            skip_reason=None,
            warnings=warnings,
        )

    def create_motion_evidence(
        self,
        payload: MotionEvidenceCreateRequest,
    ) -> MotionEvidenceResponse:
        with self.session_factory() as session:
            with session.begin():
                zone_model = session.get(ZoneModel, payload.zone_id)
                if zone_model is None:
                    raise ValueError("missing_zone")

                stream_id = payload.stream_id or zone_model.stream_id
                stream_model = session.get(StreamModel, stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")
                if zone_model.stream_id != stream_model.id:
                    raise ValueError("zone_stream_mismatch")

                source_id = payload.source_id or stream_model.source_id
                if source_id is not None:
                    source_model = session.get(CameraSourceModel, source_id)
                    if source_model is None:
                        raise ValueError("missing_source")
                    if stream_model.source_id != source_id:
                        raise ValueError("stream_source_mismatch")

                snapshot_media_asset_id = (
                    payload.snapshot_media_asset_id.strip()
                    if payload.snapshot_media_asset_id and payload.snapshot_media_asset_id.strip()
                    else None
                )
                if snapshot_media_asset_id is not None:
                    asset_model = session.get(MediaAssetModel, snapshot_media_asset_id)
                    if asset_model is None:
                        raise ValueError("missing_media_asset")
                    if asset_model.stream_id != stream_model.id:
                        raise ValueError("media_stream_mismatch")

                evidence_model = MotionEvidenceModel(
                    id=self._next_id(session, MotionEvidenceModel, "motion-evidence"),
                    source_id=source_id,
                    stream_id=stream_model.id,
                    zone_id=zone_model.id,
                    start_frame_index=payload.start_frame_index,
                    end_frame_index=payload.end_frame_index,
                    best_frame_index=payload.best_frame_index,
                    start_time=payload.start_time.strip() if payload.start_time else None,
                    end_time=payload.end_time.strip() if payload.end_time else None,
                    best_frame_time=(
                        payload.best_frame_time.strip() if payload.best_frame_time else None
                    ),
                    peak_changed_ratio=payload.peak_changed_ratio,
                    triggered_frame_count=payload.triggered_frame_count,
                    scoring_config_json=json.dumps(payload.scoring_config, sort_keys=True),
                    snapshot_media_asset_id=snapshot_media_asset_id,
                    status=MotionEvidenceStatus.pending.value,
                    promoted_event_id=None,
                    promoted_visit_id=None,
                    created_at=datetime.now(UTC),
                    notes=payload.notes.strip() if payload.notes and payload.notes.strip() else None,
                )
                session.add(evidence_model)
                session.flush()
                return _motion_evidence_from_model(evidence_model)

    def list_motion_evidence(
        self,
        *,
        status: MotionEvidenceStatus | None = None,
        zone_id: str | None = None,
    ) -> list[MotionEvidenceResponse]:
        with self.session_factory() as session:
            query = select(MotionEvidenceModel)
            if status is not None:
                query = query.where(MotionEvidenceModel.status == status.value)
            if zone_id is not None:
                query = query.where(MotionEvidenceModel.zone_id == zone_id)
            evidence_models = session.scalars(
                query.order_by(MotionEvidenceModel.created_at, MotionEvidenceModel.id)
            ).all()
            return [_motion_evidence_from_model(evidence) for evidence in evidence_models]

    def get_motion_evidence(self, evidence_id: str) -> MotionEvidenceResponse | None:
        with self.session_factory() as session:
            evidence_model = session.get(MotionEvidenceModel, evidence_id)
            return _motion_evidence_from_model(evidence_model) if evidence_model else None

    def ignore_motion_evidence(self, evidence_id: str) -> MotionEvidenceResponse | None:
        with self.session_factory() as session:
            with session.begin():
                evidence_model = session.get(MotionEvidenceModel, evidence_id)
                if evidence_model is None:
                    return None
                if evidence_model.status != MotionEvidenceStatus.pending.value:
                    raise ValueError("motion_evidence_not_pending")

                evidence_model.status = MotionEvidenceStatus.ignored.value
                session.flush()
                return _motion_evidence_from_model(evidence_model)

    def attach_motion_evidence_media(
        self,
        evidence_id: str,
        snapshot_media_asset_id: str | None,
    ) -> MotionEvidenceResponse | None:
        with self.session_factory() as session:
            with session.begin():
                evidence_model = session.get(MotionEvidenceModel, evidence_id)
                if evidence_model is None:
                    return None
                if evidence_model.status == MotionEvidenceStatus.ignored.value:
                    raise ValueError("motion_evidence_attach_ignored")
                if evidence_model.status == MotionEvidenceStatus.promoted.value:
                    raise ValueError("motion_evidence_attach_promoted")
                if evidence_model.status != MotionEvidenceStatus.pending.value:
                    raise ValueError("motion_evidence_attach_not_pending")

                media_id = (
                    snapshot_media_asset_id.strip()
                    if snapshot_media_asset_id and snapshot_media_asset_id.strip()
                    else None
                )
                if media_id is not None:
                    asset_model = session.get(MediaAssetModel, media_id)
                    if asset_model is None:
                        raise ValueError("missing_media_asset")
                    if asset_model.stream_id != evidence_model.stream_id:
                        raise ValueError("media_stream_mismatch")

                evidence_model.snapshot_media_asset_id = media_id
                session.flush()
                return _motion_evidence_from_model(evidence_model)

    def promote_motion_evidence(
        self,
        evidence_id: str,
        payload: MotionEvidencePromoteRequest,
    ) -> MotionEvidencePromoteResponse | None:
        with self.session_factory() as session:
            with session.begin():
                evidence_model = session.get(MotionEvidenceModel, evidence_id)
                if evidence_model is None:
                    return None
                if evidence_model.status == MotionEvidenceStatus.ignored.value:
                    raise ValueError("motion_evidence_ignored")
                if evidence_model.status == MotionEvidenceStatus.promoted.value:
                    raise ValueError("motion_evidence_already_promoted")
                if evidence_model.status != MotionEvidenceStatus.pending.value:
                    raise ValueError("motion_evidence_promote_not_pending")
                if not payload.create_event and not payload.create_visit:
                    raise ValueError("motion_evidence_promote_empty")
                if payload.create_visit and not payload.create_event:
                    raise ValueError("motion_evidence_visit_requires_event")

                zone_model = session.get(ZoneModel, evidence_model.zone_id)
                if zone_model is None:
                    raise ValueError("missing_zone")
                if zone_model.zone_type in {
                    ZoneType.privacy.value,
                    ZoneType.ignore.value,
                }:
                    raise ValueError("motion_evidence_zone_blocked")

                stream_model = session.get(StreamModel, evidence_model.stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")

                snapshot_media_asset_id = (
                    payload.attach_snapshot_media_asset_id
                    or evidence_model.snapshot_media_asset_id
                )
                asset_model: MediaAssetModel | None = None
                if snapshot_media_asset_id is not None:
                    asset_model = session.get(MediaAssetModel, snapshot_media_asset_id)
                    if asset_model is None:
                        raise ValueError("missing_media_asset")
                    if asset_model.stream_id != stream_model.id:
                        raise ValueError("media_stream_mismatch")
                    evidence_model.snapshot_media_asset_id = snapshot_media_asset_id

                created_at = datetime.now(UTC)
                event_id: str | None = None
                visit_id: str | None = None

                if payload.create_event:
                    event_id = self._next_id(session, EventModel, "event-motion")
                    event_title = (
                        payload.event_title.strip()
                        if payload.event_title and payload.event_title.strip()
                        else f"Motion evidence in {zone_model.name}"
                    )
                    event_model = EventModel(
                        id=event_id,
                        stream_id=stream_model.id,
                        title=event_title,
                        event_type="motion_evidence",
                        started_at=created_at,
                        ended_at=created_at,
                        primary_zone_id=zone_model.id,
                        review_status=ReviewStatus.needs_review.value,
                    )
                    session.add(event_model)

                if payload.create_visit:
                    visit_id = self._next_id(session, VisitModel, "visit-motion")
                    visit_label = (
                        payload.visit_label_hint.strip()
                        if payload.visit_label_hint and payload.visit_label_hint.strip()
                        else "unknown_animal"
                    )
                    visit_model = VisitModel(
                        id=visit_id,
                        event_id=event_id,
                        subject_label=visit_label,
                        species_guess=None,
                        confidence=None,
                        reviewed_label=None,
                        review_status=ReviewStatus.needs_review.value,
                        representative_media_path=(
                            asset_model.local_path if asset_model is not None else None
                        ),
                    )
                    session.add(visit_model)

                if payload.notes and payload.notes.strip():
                    promotion_note = payload.notes.strip()
                    evidence_model.notes = (
                        f"{evidence_model.notes}\nPromotion note: {promotion_note}"
                        if evidence_model.notes
                        else promotion_note
                    )
                evidence_model.status = MotionEvidenceStatus.promoted.value
                evidence_model.promoted_event_id = event_id
                evidence_model.promoted_visit_id = visit_id
                session.flush()

                return MotionEvidencePromoteResponse(
                    evidence=_motion_evidence_from_model(evidence_model),
                    event_id=event_id,
                    visit_id=visit_id,
                )

    def create_species_suggestion(
        self,
        payload: SpeciesSuggestionCreateRequest,
    ) -> SpeciesSuggestionResponse:
        with self.session_factory() as session:
            with session.begin():
                source_id = _clean_optional_text(payload.source_id)
                stream_id = _clean_optional_text(payload.stream_id)
                event_id = _clean_optional_text(payload.event_id)
                visit_id = _clean_optional_text(payload.visit_id)
                media_asset_id = _clean_optional_text(payload.media_asset_id)
                motion_evidence_id = _clean_optional_text(payload.motion_evidence_id)

                if source_id is not None and session.get(CameraSourceModel, source_id) is None:
                    raise ValueError("missing_source")
                if stream_id is not None and session.get(StreamModel, stream_id) is None:
                    raise ValueError("missing_stream")
                if event_id is not None and session.get(EventModel, event_id) is None:
                    raise ValueError("missing_event")
                if visit_id is not None and session.get(VisitModel, visit_id) is None:
                    raise ValueError("missing_visit")
                if (
                    media_asset_id is not None
                    and session.get(MediaAssetModel, media_asset_id) is None
                ):
                    raise ValueError("missing_media_asset")
                if (
                    motion_evidence_id is not None
                    and session.get(MotionEvidenceModel, motion_evidence_id) is None
                ):
                    raise ValueError("missing_motion_evidence")

                suggestion_model = SpeciesSuggestionModel(
                    id=self._next_id(session, SpeciesSuggestionModel, "species-suggestion"),
                    source_id=source_id,
                    stream_id=stream_id,
                    event_id=event_id,
                    visit_id=visit_id,
                    media_asset_id=media_asset_id,
                    motion_evidence_id=motion_evidence_id,
                    adapter_id=payload.adapter_id.strip(),
                    adapter_name=payload.adapter_name.strip(),
                    suggested_label=payload.suggested_label.strip(),
                    suggested_common_name=_clean_optional_text(payload.suggested_common_name),
                    suggested_scientific_name=_clean_optional_text(
                        payload.suggested_scientific_name
                    ),
                    confidence=payload.confidence,
                    rank=payload.rank,
                    alternatives_json=json.dumps(payload.alternatives, sort_keys=True),
                    evidence_region_json=(
                        json.dumps(payload.evidence_region, sort_keys=True)
                        if payload.evidence_region is not None
                        else None
                    ),
                    status=SpeciesSuggestionStatus.pending.value,
                    created_at=datetime.now(UTC),
                    notes=_clean_optional_text(payload.notes),
                )
                session.add(suggestion_model)
                session.flush()
                return _species_suggestion_from_model(suggestion_model)

    def list_species_suggestions(
        self,
        *,
        status: SpeciesSuggestionStatus | None = None,
        visit_id: str | None = None,
        event_id: str | None = None,
        media_asset_id: str | None = None,
        suggested_label: str | None = None,
    ) -> list[SpeciesSuggestionResponse]:
        with self.session_factory() as session:
            query = select(SpeciesSuggestionModel)
            if status is not None:
                query = query.where(SpeciesSuggestionModel.status == status.value)
            normalized_visit_id = _clean_optional_text(visit_id)
            if normalized_visit_id is not None:
                query = query.where(SpeciesSuggestionModel.visit_id == normalized_visit_id)
            normalized_event_id = _clean_optional_text(event_id)
            if normalized_event_id is not None:
                query = query.where(SpeciesSuggestionModel.event_id == normalized_event_id)
            normalized_media_asset_id = _clean_optional_text(media_asset_id)
            if normalized_media_asset_id is not None:
                query = query.where(
                    SpeciesSuggestionModel.media_asset_id == normalized_media_asset_id
                )
            normalized_label = _clean_optional_text(suggested_label)
            if normalized_label is not None:
                query = query.where(SpeciesSuggestionModel.suggested_label == normalized_label)

            suggestion_models = session.scalars(
                query.order_by(
                    SpeciesSuggestionModel.created_at,
                    SpeciesSuggestionModel.rank,
                    SpeciesSuggestionModel.id,
                )
            ).all()
            return [
                _species_suggestion_from_model(suggestion)
                for suggestion in suggestion_models
            ]

    def get_species_suggestion(self, suggestion_id: str) -> SpeciesSuggestionResponse | None:
        with self.session_factory() as session:
            suggestion_model = session.get(SpeciesSuggestionModel, suggestion_id)
            return (
                _species_suggestion_from_model(suggestion_model)
                if suggestion_model
                else None
            )

    def update_species_suggestion_status(
        self,
        suggestion_id: str,
        payload: SpeciesSuggestionStatusUpdateRequest,
    ) -> SpeciesSuggestionResponse | None:
        with self.session_factory() as session:
            with session.begin():
                suggestion_model = session.get(SpeciesSuggestionModel, suggestion_id)
                if suggestion_model is None:
                    return None
                if suggestion_model.status != SpeciesSuggestionStatus.pending.value:
                    raise ValueError("species_suggestion_not_pending")

                suggestion_model.status = payload.status.value
                session.flush()
                return _species_suggestion_from_model(suggestion_model)

    def list_model_adapters(self) -> list[ModelAdapter]:
        return [adapter.model_copy(deep=True) for adapter in _model_adapters()]

    def get_model_adapter(self, adapter_id: str) -> ModelAdapter | None:
        adapter = _model_adapter_by_id(adapter_id)
        return adapter.model_copy(deep=True) if adapter else None

    def model_adapter_evaluation_summary(
        self,
        adapter_id: str | None = None,
    ) -> AdapterEvaluationSummary:
        adapter_filter = _model_adapter_by_id(adapter_id) if adapter_id else None
        if adapter_id is not None and adapter_filter is None:
            raise ValueError("missing_adapter")

        with self.session_factory() as session:
            proposal_models = session.scalars(
                select(DetectionProposalModel).order_by(
                    DetectionProposalModel.created_at,
                    DetectionProposalModel.id,
                )
            ).all()
            items: list[AdapterEvaluationItem] = []
            converted_count = 0

            for proposal_model in proposal_models:
                run_model = session.get(DetectionRunModel, proposal_model.run_id)
                adapter = _model_adapter_for_detection_run(run_model)
                if adapter_filter is not None and (
                    adapter is None or adapter.id != adapter_filter.id
                ):
                    continue

                if proposal_model.event_id is not None or proposal_model.visit_id is not None:
                    converted_count += 1

                items.append(
                    self._adapter_evaluation_item(
                        session,
                        proposal_model=proposal_model,
                        adapter=adapter,
                    )
                )

            outcome_counts = Counter(item.outcome for item in items)
            matched_count = outcome_counts[AdapterEvaluationOutcome.matched_reviewed_truth]
            mismatched_count = outcome_counts[AdapterEvaluationOutcome.mismatched_reviewed_truth]
            unknown_reviewed_count = outcome_counts[
                AdapterEvaluationOutcome.unknown_reviewed_label
            ]
            reviewed_count = matched_count + mismatched_count + unknown_reviewed_count
            unreviewed_count = (
                outcome_counts[AdapterEvaluationOutcome.awaiting_review]
                + outcome_counts[AdapterEvaluationOutcome.converted_needs_review]
            )
            match_denominator = matched_count + mismatched_count

            return AdapterEvaluationSummary(
                adapter_id=adapter_filter.id if adapter_filter else None,
                adapter_name=adapter_filter.name if adapter_filter else None,
                proposal_count=len(items),
                reviewed_count=reviewed_count,
                unreviewed_count=unreviewed_count,
                matched_count=matched_count,
                mismatched_count=mismatched_count,
                rejected_count=outcome_counts[AdapterEvaluationOutcome.rejected_evidence],
                converted_count=converted_count,
                unknown_reviewed_count=unknown_reviewed_count,
                match_rate=(
                    matched_count / match_denominator
                    if match_denominator > 0
                    else None
                ),
                items=items,
                generated_at=datetime.now(UTC),
                local_first_note=(
                    "Adapter evaluation is a local readiness signal. Proposal labels "
                    "are evidence; reviewed corrections are truth. Match rate only uses "
                    "reviewed non-unknown labels and is not a deployment score."
                ),
            )

    def model_readiness_summary(self) -> ModelReadinessSummary:
        coverage = self.dataset_coverage_summary()
        quality = self.dataset_quality_summary()
        evaluation = self.model_adapter_evaluation_summary()
        taxonomy_count = len(self.list_taxonomy_labels())
        adapters = self.list_model_adapters()
        adapter_contract_ready = bool(adapters) and all(
            not adapter.creates_review_truth for adapter in adapters
        )
        ready_for_first_detector_spike = (
            coverage.export_ready_count > 0
            and quality.high_count == 0
            and taxonomy_count > 0
            and adapter_contract_ready
        )

        return ModelReadinessSummary(
            reviewed_record_count=coverage.reviewed_record_count,
            export_ready_count=coverage.export_ready_count,
            dataset_quality_issue_count=quality.issue_count,
            high_quality_issue_count=quality.high_count,
            reviewed_species_count=coverage.reviewed_species_count,
            target_species_count=coverage.target_species_count,
            covered_target_species_count=coverage.covered_target_species_count,
            missing_target_species_count=coverage.missing_target_species_count,
            adapter_proposal_count=evaluation.proposal_count,
            adapter_reviewed_count=evaluation.reviewed_count,
            adapter_match_rate=evaluation.match_rate,
            ready_for_first_detector_spike=ready_for_first_detector_spike,
            recommended_next_step=_model_readiness_next_step(
                coverage=coverage,
                quality=quality,
                taxonomy_count=taxonomy_count,
                adapter_contract_ready=adapter_contract_ready,
            ),
            checklist=_model_readiness_checklist(
                coverage=coverage,
                quality=quality,
                evaluation=evaluation,
                taxonomy_count=taxonomy_count,
                adapter_contract_ready=adapter_contract_ready,
            ),
            generated_at=datetime.now(UTC),
            local_first_note=(
                "Pre-model readiness combines reviewed local dataset coverage, QA, "
                "and adapter evidence guardrails. It does not run ML or inspect media. "
                "Future detectors must create DetectionProposal evidence and user "
                "corrections remain dataset truth."
            ),
        )

    def run_model_adapter(
        self,
        adapter_id: str,
        payload: ModelAdapterRunRequest,
    ) -> ModelAdapterRunResult:
        adapter = _model_adapter_by_id(adapter_id)
        if adapter is None:
            raise ValueError("missing_adapter")
        if payload.adapter_id != adapter_id:
            raise ValueError("adapter_mismatch")
        if adapter_id == LOCAL_IMAGE_DETECTOR_ID:
            return self._run_local_image_detector_adapter(adapter, payload)
        if adapter_id == MEGADETECTOR_ADAPTER_ID:
            return self._run_megadetector_adapter(adapter, payload)
        if adapter.status != ModelAdapterStatus.available:
            raise ValueError("adapter_unavailable")

        with self.session_factory() as session:
            with session.begin():
                asset_model = session.get(MediaAssetModel, payload.media_asset_id)
                if asset_model is None:
                    raise ValueError("missing_media_asset")
                if asset_model.media_type not in adapter.supported_media_types:
                    raise ValueError("unsupported_media_type")

                stream_model = session.get(StreamModel, asset_model.stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")

                zone_models: list[ZoneModel | None]
                if payload.zone_ids:
                    zone_models = []
                    seen_zone_ids: set[str] = set()
                    for zone_id in payload.zone_ids:
                        if zone_id in seen_zone_ids:
                            continue
                        seen_zone_ids.add(zone_id)
                        zone_models.append(
                            self._resolve_import_zone(session, zone_id, stream_model.id)
                        )
                else:
                    zone_models = [self._default_demo_zone(session, stream_model.id)]

                requested_labels = [
                    label.strip()
                    for label in payload.requested_labels or []
                    if label.strip()
                ] or ["unknown_bird"]
                created_at = datetime.now(UTC)
                run_model = DetectionRunModel(
                    id=self._next_id(session, DetectionRunModel, "detection-run"),
                    media_asset_id=asset_model.id,
                    source=DetectionSource.demo_rule.value,
                    summary=(
                        f"Model adapter contract run for {adapter.name} ({adapter.id}); "
                        "proposal evidence only, no media analysis."
                    ),
                    status=DetectionRunStatus.completed.value,
                    created_at=created_at,
                    completed_at=created_at,
                )
                session.add(run_model)

                proposal_models: list[DetectionProposalModel] = []
                for zone_model in zone_models:
                    for requested_label in requested_labels:
                        normalized_label = self._normalize_label_from_session(
                            session,
                            requested_label,
                        )
                        suggested_subject_label, suggested_species = (
                            self._adapter_subject_and_species(session, normalized_label)
                        )
                        proposal_model = DetectionProposalModel(
                            id=self._next_id(
                                session,
                                DetectionProposalModel,
                                "detection-proposal",
                            ),
                            run_id=run_model.id,
                            media_asset_id=asset_model.id,
                            stream_id=stream_model.id,
                            zone_id=zone_model.id if zone_model else None,
                            event_id=None,
                            visit_id=None,
                            label=normalized_label,
                            confidence=0.62,
                            bbox_json=None,
                            suggested_event_type="animal_visit",
                            suggested_subject_label=suggested_subject_label,
                            suggested_species=suggested_species,
                            status=DetectionProposalStatus.proposed.value,
                            notes=(
                                payload.notes.strip()
                                if payload.notes and payload.notes.strip()
                                else (
                                    "Model adapter contract generated proposal evidence; "
                                    "review and correction remain required."
                                )
                            ),
                            created_at=created_at,
                            decided_at=None,
                        )
                        session.add(proposal_model)
                        session.flush()
                        proposal_models.append(proposal_model)

                session.flush()
                return ModelAdapterRunResult(
                    adapter=adapter.model_copy(deep=True),
                    detection_run=_detection_run_from_model(run_model),
                    proposals=[
                        _detection_proposal_from_model(proposal)
                        for proposal in proposal_models
                    ],
                    review_queue_count=len(self._review_queue_items(session)),
                    local_first_note=(
                        "Model adapters create proposal evidence, not review truth. "
                        "Users must convert, review, and correct proposals before exports, "
                        "coverage, or QA treat labels as dataset truth."
                    ),
                )

    def _run_local_image_detector_adapter(
        self,
        adapter: ModelAdapter,
        payload: ModelAdapterRunRequest,
    ) -> ModelAdapterRunResult:
        with self.session_factory() as session:
            with session.begin():
                asset_model = session.get(MediaAssetModel, payload.media_asset_id)
                if asset_model is None:
                    raise ValueError("missing_media_asset")
                if (
                    asset_model.media_type != "image"
                    or asset_model.content_type not in SUPPORTED_IMAGE_CONTENT_TYPES
                ):
                    raise ValueError("local_detector_unsupported_media_type")

                stream_model = session.get(StreamModel, asset_model.stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")

                if not Path(asset_model.local_path).exists():
                    raise ValueError("missing_media_file")

                zone_model: ZoneModel | None = None
                if payload.zone_ids:
                    zone_model = self._resolve_import_zone(
                        session,
                        payload.zone_ids[0],
                        stream_model.id,
                    )
                else:
                    zone_model = self._default_demo_zone(session, stream_model.id)

                try:
                    detector_proposals = run_local_image_detector(
                        local_path=asset_model.local_path,
                        content_type=asset_model.content_type,
                    )
                except LocalDetectorConfigurationError as error:
                    raise ValueError("local_detector_not_configured") from error
                except LocalDetectorRuntimeUnavailableError as error:
                    raise ValueError("local_detector_runtime_unavailable") from error
                except LocalDetectorUnsupportedMediaError as error:
                    if str(error) == "missing_media_file":
                        raise ValueError("missing_media_file") from error
                    raise ValueError("local_detector_unsupported_media_type") from error
                except LocalDetectorOutputError as error:
                    raise ValueError(str(error) or "unsupported_detector_output") from error

                created_at = datetime.now(UTC)
                run_model = DetectionRunModel(
                    id=self._next_id(session, DetectionRunModel, "detection-run"),
                    media_asset_id=asset_model.id,
                    source=DetectionSource.future_model.value,
                    summary=(
                        f"Model adapter contract run for {adapter.name} ({adapter.id}); "
                        "local image detector proposal evidence only."
                    ),
                    status=DetectionRunStatus.completed.value,
                    created_at=created_at,
                    completed_at=created_at,
                )
                session.add(run_model)
                session.flush()

                proposal_models: list[DetectionProposalModel] = []
                for detector_proposal in detector_proposals:
                    normalized_label = self._normalize_label_from_session(
                        session,
                        detector_proposal.label,
                    )
                    suggested_subject_label, suggested_species = (
                        self._adapter_subject_and_species(session, normalized_label)
                    )
                    proposal_model = DetectionProposalModel(
                        id=self._next_id(
                            session,
                            DetectionProposalModel,
                            "detection-proposal",
                        ),
                        run_id=run_model.id,
                        media_asset_id=asset_model.id,
                        stream_id=stream_model.id,
                        zone_id=zone_model.id if zone_model else None,
                        event_id=None,
                        visit_id=None,
                        label=normalized_label,
                        confidence=detector_proposal.confidence,
                        bbox_json=_detector_bbox_to_json(detector_proposal.bbox),
                        suggested_event_type="animal_visit",
                        suggested_subject_label=suggested_subject_label,
                        suggested_species=suggested_species,
                        status=DetectionProposalStatus.proposed.value,
                        notes=(
                            payload.notes.strip()
                            if payload.notes and payload.notes.strip()
                            else (
                                "Local image detector generated proposal evidence; "
                                "review and correction remain required."
                            )
                        ),
                        created_at=created_at,
                        decided_at=None,
                    )
                    session.add(proposal_model)
                    session.flush()
                    proposal_models.append(proposal_model)

                return ModelAdapterRunResult(
                    adapter=adapter.model_copy(deep=True),
                    detection_run=_detection_run_from_model(run_model),
                    proposals=[
                        _detection_proposal_from_model(proposal)
                        for proposal in proposal_models
                    ],
                    review_queue_count=len(self._review_queue_items(session)),
                    local_first_note=(
                        "Local image detector outputs are proposal evidence only. "
                        "Convert, review, and correct proposals before exports, coverage, "
                        "QA, or analytics treat labels as dataset truth."
                    )
                    if proposal_models
                    else (
                        "Local image detector completed with no proposal evidence. "
                        "No events, visits, review labels, or dataset truth were created."
                    ),
                )

    def _run_megadetector_adapter(
        self,
        adapter: ModelAdapter,
        payload: ModelAdapterRunRequest,
    ) -> ModelAdapterRunResult:
        with self.session_factory() as session:
            with session.begin():
                asset_model = session.get(MediaAssetModel, payload.media_asset_id)
                if asset_model is None:
                    raise ValueError("missing_media_asset")
                if (
                    asset_model.media_type != "image"
                    or asset_model.content_type not in SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES
                ):
                    raise ValueError("megadetector_unsupported_media_type")

                stream_model = session.get(StreamModel, asset_model.stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")

                if not Path(asset_model.local_path).exists():
                    raise ValueError("missing_media_file")

                zone_model: ZoneModel | None = None
                if payload.zone_ids:
                    zone_model = self._resolve_import_zone(
                        session,
                        payload.zone_ids[0],
                        stream_model.id,
                    )
                else:
                    zone_model = self._default_demo_zone(session, stream_model.id)

                try:
                    detector_proposals = run_megadetector_on_image(
                        local_path=asset_model.local_path,
                        content_type=asset_model.content_type,
                        zone_context=zone_model.id if zone_model else None,
                    )
                except MegaDetectorModelFileError as error:
                    raise ValueError("megadetector_model_file_missing") from error
                except MegaDetectorConfigurationError as error:
                    raise ValueError("megadetector_not_configured") from error
                except MegaDetectorRuntimeUnavailableError as error:
                    raise ValueError("megadetector_runtime_unavailable") from error
                except MegaDetectorUnsupportedMediaError as error:
                    if str(error) == "missing_media_file":
                        raise ValueError("missing_media_file") from error
                    raise ValueError("megadetector_unsupported_media_type") from error
                except MegaDetectorOutputError as error:
                    raise ValueError(str(error) or "unsupported_detector_output") from error

                created_at = datetime.now(UTC)
                run_model = DetectionRunModel(
                    id=self._next_id(session, DetectionRunModel, "detection-run"),
                    media_asset_id=asset_model.id,
                    source=DetectionSource.future_model.value,
                    summary=(
                        f"Model adapter contract run for {adapter.name} ({adapter.id}); "
                        "MegaDetector-family proposal evidence only."
                    ),
                    status=DetectionRunStatus.completed.value,
                    created_at=created_at,
                    completed_at=created_at,
                )
                session.add(run_model)
                session.flush()

                proposal_models: list[DetectionProposalModel] = []
                for detector_proposal in detector_proposals:
                    mapped_label = normalize_megadetector_label(detector_proposal.label)
                    normalized_label = self._normalize_label_from_session(session, mapped_label)
                    suggested_subject_label, suggested_species = (
                        self._adapter_subject_and_species(session, normalized_label)
                    )
                    proposal_model = DetectionProposalModel(
                        id=self._next_id(
                            session,
                            DetectionProposalModel,
                            "detection-proposal",
                        ),
                        run_id=run_model.id,
                        media_asset_id=asset_model.id,
                        stream_id=stream_model.id,
                        zone_id=zone_model.id if zone_model else None,
                        event_id=None,
                        visit_id=None,
                        label=normalized_label,
                        confidence=detector_proposal.confidence,
                        bbox_json=_detector_bbox_to_json(detector_proposal.bbox),
                        suggested_event_type="animal_visit",
                        suggested_subject_label=suggested_subject_label,
                        suggested_species=suggested_species,
                        status=DetectionProposalStatus.proposed.value,
                        notes=(
                            payload.notes.strip()
                            if payload.notes and payload.notes.strip()
                            else (
                                "MegaDetector-family adapter generated proposal evidence; "
                                "review and correction remain required."
                            )
                        ),
                        created_at=created_at,
                        decided_at=None,
                    )
                    session.add(proposal_model)
                    session.flush()
                    proposal_models.append(proposal_model)

                return ModelAdapterRunResult(
                    adapter=adapter.model_copy(deep=True),
                    detection_run=_detection_run_from_model(run_model),
                    proposals=[
                        _detection_proposal_from_model(proposal)
                        for proposal in proposal_models
                    ],
                    review_queue_count=len(self._review_queue_items(session)),
                    local_first_note=(
                        "MegaDetector-family outputs are animal/person/vehicle proposal "
                        "evidence only. Convert, review, and correct proposals before "
                        "exports, coverage, QA, or analytics treat labels as dataset truth."
                    )
                    if proposal_models
                    else (
                        "MegaDetector-family adapter completed with no proposal evidence. "
                        "No events, visits, review labels, or dataset truth were created."
                    ),
                )

    def list_detection_runs(self) -> list[DetectionRun]:
        with self.session_factory() as session:
            runs = session.scalars(
                select(DetectionRunModel).order_by(
                    DetectionRunModel.created_at,
                    DetectionRunModel.id,
                )
            ).all()
            return [_detection_run_from_model(run) for run in runs]

    def get_detection_run(self, run_id: str) -> DetectionRun | None:
        with self.session_factory() as session:
            run = session.get(DetectionRunModel, run_id)
            return _detection_run_from_model(run) if run else None

    def create_detection_run(self, payload: DetectionRunCreate) -> DetectionRun:
        with self.session_factory() as session:
            with session.begin():
                if session.get(MediaAssetModel, payload.media_asset_id) is None:
                    raise ValueError("missing_media_asset")

                created_at = datetime.now(UTC)
                run_model = DetectionRunModel(
                    id=self._next_id(session, DetectionRunModel, "detection-run"),
                    media_asset_id=payload.media_asset_id,
                    source=payload.source.value,
                    summary=(
                        payload.summary.strip()
                        if payload.summary and payload.summary.strip()
                        else None
                    ),
                    status=DetectionRunStatus.completed.value,
                    created_at=created_at,
                    completed_at=created_at,
                )
                session.add(run_model)
                session.flush()
                return _detection_run_from_model(run_model)

    def create_demo_detection_run(
        self,
        payload: DemoDetectionRunCreate,
    ) -> DemoDetectionRunResult:
        with self.session_factory() as session:
            with session.begin():
                asset_model = session.get(MediaAssetModel, payload.media_asset_id)
                if asset_model is None:
                    raise ValueError("missing_media_asset")

                stream_model = session.get(StreamModel, asset_model.stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")

                zone_model = (
                    self._resolve_import_zone(session, payload.zone_id, stream_model.id)
                    if payload.zone_id
                    else self._default_demo_zone(session, stream_model.id)
                )
                created_at = datetime.now(UTC)
                run_model = DetectionRunModel(
                    id=self._next_id(session, DetectionRunModel, "detection-run"),
                    media_asset_id=asset_model.id,
                    source=DetectionSource.demo_rule.value,
                    summary="Demo detector proposal generation without media analysis.",
                    status=DetectionRunStatus.completed.value,
                    created_at=created_at,
                    completed_at=created_at,
                )
                proposal_model = DetectionProposalModel(
                    id=self._next_id(session, DetectionProposalModel, "detection-proposal"),
                    run_id=run_model.id,
                    media_asset_id=asset_model.id,
                    stream_id=stream_model.id,
                    zone_id=zone_model.id if zone_model else None,
                    event_id=None,
                    visit_id=None,
                    label=payload.label.strip() or "bird",
                    confidence=payload.confidence,
                    bbox_json=None,
                    suggested_event_type="animal_visit",
                    suggested_subject_label=(
                        payload.suggested_subject_label.strip() or "unknown_bird"
                    ),
                    suggested_species=(
                        payload.suggested_species.strip()
                        if payload.suggested_species and payload.suggested_species.strip()
                        else None
                    ),
                    status=DetectionProposalStatus.proposed.value,
                    notes=(
                        payload.notes.strip()
                        if payload.notes and payload.notes.strip()
                        else "Demo proposal generated without running a model."
                    ),
                    created_at=created_at,
                    decided_at=None,
                )
                session.add_all([run_model, proposal_model])
                session.flush()
                return DemoDetectionRunResult(
                    detection_run=_detection_run_from_model(run_model),
                    proposals=[_detection_proposal_from_model(proposal_model)],
                    review_queue_count=len(self._review_queue_items(session)),
                )

    def list_detection_proposals(self) -> list[DetectionProposal]:
        with self.session_factory() as session:
            proposals = session.scalars(
                select(DetectionProposalModel).order_by(
                    DetectionProposalModel.created_at,
                    DetectionProposalModel.id,
                )
            ).all()
            return [_detection_proposal_from_model(proposal) for proposal in proposals]

    def get_detection_proposal(self, proposal_id: str) -> DetectionProposal | None:
        with self.session_factory() as session:
            proposal = session.get(DetectionProposalModel, proposal_id)
            return _detection_proposal_from_model(proposal) if proposal else None

    def detection_proposals_for_event(self, event_id: str) -> list[DetectionProposal]:
        with self.session_factory() as session:
            proposals = session.scalars(
                select(DetectionProposalModel)
                .where(DetectionProposalModel.event_id == event_id)
                .order_by(DetectionProposalModel.created_at, DetectionProposalModel.id)
            ).all()
            return [_detection_proposal_from_model(proposal) for proposal in proposals]

    def detection_proposals_for_visit(self, visit_id: str) -> list[DetectionProposal]:
        with self.session_factory() as session:
            proposals = session.scalars(
                select(DetectionProposalModel)
                .where(DetectionProposalModel.visit_id == visit_id)
                .order_by(DetectionProposalModel.created_at, DetectionProposalModel.id)
            ).all()
            return [_detection_proposal_from_model(proposal) for proposal in proposals]

    def detection_proposals_for_run(self, run_id: str) -> list[DetectionProposal] | None:
        with self.session_factory() as session:
            if session.get(DetectionRunModel, run_id) is None:
                return None

            proposals = session.scalars(
                select(DetectionProposalModel)
                .where(DetectionProposalModel.run_id == run_id)
                .order_by(DetectionProposalModel.created_at, DetectionProposalModel.id)
            ).all()
            return [_detection_proposal_from_model(proposal) for proposal in proposals]

    def create_detection_proposal(
        self,
        payload: DetectionProposalCreate,
    ) -> DetectionProposal:
        with self.session_factory() as session:
            with session.begin():
                asset_model = session.get(MediaAssetModel, payload.media_asset_id)
                if asset_model is None:
                    raise ValueError("missing_media_asset")

                stream_id = payload.stream_id or asset_model.stream_id
                stream_model = session.get(StreamModel, stream_id)
                if stream_model is None:
                    raise ValueError("missing_stream")
                if asset_model.stream_id != stream_id:
                    raise ValueError("media_stream_mismatch")

                zone_model = self._resolve_import_zone(session, payload.zone_id, stream_id)
                created_at = datetime.now(UTC)
                run_model = DetectionRunModel(
                    id=self._next_id(session, DetectionRunModel, "detection-run"),
                    media_asset_id=asset_model.id,
                    source=DetectionSource.manual.value,
                    summary="Manual detection proposal from local media input.",
                    status=DetectionRunStatus.completed.value,
                    created_at=created_at,
                    completed_at=created_at,
                )
                proposal_model = DetectionProposalModel(
                    id=self._next_id(session, DetectionProposalModel, "detection-proposal"),
                    run_id=run_model.id,
                    media_asset_id=asset_model.id,
                    stream_id=stream_model.id,
                    zone_id=zone_model.id if zone_model else None,
                    event_id=None,
                    visit_id=None,
                    label=payload.label.strip() or "unknown_animal",
                    confidence=payload.confidence,
                    bbox_json=_bbox_to_json(payload.bbox),
                    suggested_event_type=payload.suggested_event_type.strip() or "animal_visit",
                    suggested_subject_label=(
                        payload.suggested_subject_label.strip() or "unknown_animal"
                    ),
                    suggested_species=(
                        payload.suggested_species.strip()
                        if payload.suggested_species and payload.suggested_species.strip()
                        else None
                    ),
                    status=DetectionProposalStatus.proposed.value,
                    notes=payload.notes.strip() if payload.notes and payload.notes.strip() else None,
                    created_at=created_at,
                    decided_at=None,
                )
                session.add_all([run_model, proposal_model])
                session.flush()
                return _detection_proposal_from_model(proposal_model)

    def decide_detection_proposal(
        self,
        proposal_id: str,
        payload: DetectionProposalDecisionCreate,
    ) -> DetectionProposalDecisionResult | None:
        with self.session_factory() as session:
            with session.begin():
                proposal_model = session.get(DetectionProposalModel, proposal_id)
                if proposal_model is None:
                    return None
                if proposal_model.status != DetectionProposalStatus.proposed.value:
                    raise ValueError("proposal_already_decided")

                event: Event | None = None
                visit: Visit | None = None
                decided_at = datetime.now(UTC)

                if payload.notes and payload.notes.strip():
                    proposal_model.notes = _merge_notes(proposal_model.notes, payload.notes.strip())

                if payload.decision == DetectionProposalDecision.reject:
                    proposal_model.status = DetectionProposalStatus.rejected.value
                    proposal_model.decided_at = decided_at
                elif payload.decision in {
                    DetectionProposalDecision.accept,
                    DetectionProposalDecision.convert_to_event,
                }:
                    event, visit = self._create_detection_proposal_review_records(
                        session,
                        proposal_model=proposal_model,
                        payload=payload,
                        created_at=decided_at,
                    )
                    proposal_model.status = (
                        DetectionProposalStatus.accepted.value
                        if payload.decision == DetectionProposalDecision.accept
                        else DetectionProposalStatus.converted.value
                    )
                    proposal_model.event_id = event.id
                    proposal_model.visit_id = visit.id
                    proposal_model.decided_at = decided_at
                else:
                    raise ValueError("unsupported_decision")

                session.flush()
                return DetectionProposalDecisionResult(
                    proposal=_detection_proposal_from_model(proposal_model),
                    event=event,
                    visit=visit,
                    review_queue_count=len(self._review_queue_items(session)),
                    analytics=self._analytics_summary(session),
                )

    def create_media_import(
        self,
        *,
        content: bytes,
        original_filename: str,
        content_type: str,
        stream_id: str | None = None,
        zone_id: str | None = None,
        title: str | None = None,
        subject_label: str = "unknown_animal",
        species_guess: str | None = None,
        notes: str | None = None,
    ) -> MediaImportResult:
        if not content:
            raise ValueError("empty_file")

        media_type = SUPPORTED_MEDIA_CONTENT_TYPES.get(content_type)
        if media_type is None:
            raise ValueError("unsupported_content_type")

        with self.session_factory() as session:
            with session.begin():
                stream_model = self._resolve_import_stream(session, stream_id)
                zone_model = self._resolve_import_zone(session, zone_id, stream_model.id)
                media_asset, event, visit = self._create_media_product_records(
                    session,
                    stream_model=stream_model,
                    zone_model=zone_model,
                    content=content,
                    original_filename=original_filename,
                    content_type=content_type,
                    media_type=media_type,
                    title=title,
                    event_type="manual_media_import",
                    default_title="Imported media observation",
                    subject_label=subject_label,
                    species_guess=species_guess,
                    notes=notes,
                )

                return MediaImportResult(
                    media_asset=media_asset,
                    event=event,
                    visit=visit,
                    stream=_stream_from_model(stream_model),
                    review_queue_count=len(self._review_queue_items(session)),
                )

    def preview_folder_import(self, folder_path: str) -> FolderImportPreview:
        if not folder_path.strip():
            raise ValueError("folder_required")
        folder = _folder_path(folder_path)
        return self._preview_folder_import_for_path(folder)

    def import_folder_media(self, payload: FolderImportCreate) -> FolderImportResult:
        if not payload.folder_path.strip():
            raise ValueError("folder_required")
        folder = _folder_path(payload.folder_path)
        preview = self._preview_folder_import_for_path(folder)
        candidates = preview.supported_files[: payload.limit] if payload.limit else preview.supported_files
        skipped_files = list(preview.skipped_files)

        media_assets: list[MediaAsset] = []
        events: list[Event] = []
        visits: list[Visit] = []

        with self.session_factory() as session:
            with session.begin():
                stream_model = self._resolve_import_stream(session, payload.stream_id)
                zone_model = self._resolve_import_zone(session, payload.zone_id, stream_model.id)

                for candidate in candidates:
                    source_path = Path(candidate.path)
                    try:
                        content = source_path.read_bytes()
                    except OSError:
                        skipped_files.append(
                            FolderImportSkippedFile(
                                filename=candidate.filename,
                                reason="read_error",
                            )
                        )
                        continue

                    if not content:
                        skipped_files.append(
                            FolderImportSkippedFile(
                                filename=candidate.filename,
                                reason="empty_file",
                            )
                        )
                        continue

                    media_asset, event, visit = self._create_media_product_records(
                        session,
                        stream_model=stream_model,
                        zone_model=zone_model,
                        content=content,
                        original_filename=candidate.filename,
                        content_type=candidate.content_type,
                        media_type=candidate.media_type,
                        title=f"Imported folder media: {candidate.filename}",
                        event_type="folder_media_import",
                        default_title="Imported folder media",
                        subject_label=payload.subject_label,
                        species_guess=payload.species_guess,
                        notes=payload.notes,
                    )
                    media_assets.append(media_asset)
                    events.append(event)
                    visits.append(visit)

                return FolderImportResult(
                    folder_path=str(folder),
                    imported_count=len(media_assets),
                    skipped_count=len(skipped_files),
                    media_assets=media_assets,
                    events=events,
                    visits=visits,
                    skipped_files=skipped_files,
                    review_queue_count=len(self._review_queue_items(session)),
                )

    def list_review_labels(self) -> list[ReviewLabel]:
        with self.session_factory() as session:
            labels = session.scalars(
                select(ReviewLabelModel).order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
            ).all()
            return [_review_label_from_model(label) for label in labels]

    def review_labels_for_event(self, event_id: str) -> list[ReviewLabel]:
        with self.session_factory() as session:
            return self._review_labels_for_event(session, event_id)

    def review_labels_for_visit(self, visit_id: str) -> list[ReviewLabel]:
        with self.session_factory() as session:
            return self._review_labels_for_visit(session, visit_id)

    def review_labels_for_event_tree(self, event_id: str) -> list[ReviewLabel]:
        with self.session_factory() as session:
            visit_ids = {visit.id for visit in self._visits_for_event(session, event_id)}
            labels = session.scalars(
                select(ReviewLabelModel).order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
            ).all()
            return [
                _review_label_from_model(label)
                for label in labels
                if (label.target_type == "event" and label.target_id == event_id)
                or (label.target_type == "visit" and label.target_id in visit_ids)
            ]

    def create_review_label(
        self,
        payload: ReviewCorrectionCreate,
        created_at: datetime | None = None,
    ) -> ReviewCorrectionResult:
        with self.session_factory() as session:
            with session.begin():
                normalized_label = self._normalize_label_from_session(session, payload.label)
                label_model = ReviewLabelModel(
                    id=self._next_id(session, ReviewLabelModel, "review-label"),
                    target_type=payload.target_type,
                    target_id=payload.target_id,
                    label=normalized_label,
                    notes=payload.notes,
                    created_at=created_at or datetime.now(UTC),
                )

                visit: Visit | None = None
                event: Event | None = None

                if payload.target_type == "visit":
                    visit_model = session.get(VisitModel, payload.target_id)
                    if visit_model is None:
                        raise ValueError("missing_visit")

                    session.add(label_model)
                    visit_model.reviewed_label = normalized_label
                    visit_model.review_status = ReviewStatus.reviewed.value

                    event_model = session.get(EventModel, visit_model.event_id)
                    if event_model is not None:
                        child_visits = self._visit_models_for_event(session, event_model.id)
                        if all(
                            child_visit.review_status != ReviewStatus.needs_review.value
                            for child_visit in child_visits
                        ):
                            event_model.review_status = ReviewStatus.reviewed.value
                        event = self._event_from_model(session, event_model)

                    visit = _visit_from_model(visit_model)

                elif payload.target_type == "event":
                    event_model = session.get(EventModel, payload.target_id)
                    if event_model is None:
                        raise ValueError("missing_event")

                    session.add(label_model)
                    event_model.review_status = ReviewStatus.reviewed.value
                    event = self._event_from_model(session, event_model)
                else:
                    raise ValueError("unsupported_target")

                session.flush()
                review_label = _review_label_from_model(label_model)
                return ReviewCorrectionResult(
                    review_label=review_label,
                    visit=visit,
                    event=event,
                    review_queue_count=len(self._review_queue_items(session)),
                    analytics=self._analytics_summary(session),
                )

    def review_queue_items(self) -> list[ReviewQueueItem]:
        with self.session_factory() as session:
            return self._review_queue_items(session)

    def list_dataset_exports(self) -> list[DatasetExport]:
        with self.session_factory() as session:
            exports = session.scalars(
                select(DatasetExportModel).order_by(
                    DatasetExportModel.created_at,
                    DatasetExportModel.id,
                )
            ).all()
            return [_dataset_export_from_model(dataset_export) for dataset_export in exports]

    def get_dataset_export(self, export_id: str) -> DatasetExport | None:
        with self.session_factory() as session:
            dataset_export = session.get(DatasetExportModel, export_id)
            return _dataset_export_from_model(dataset_export) if dataset_export else None

    def create_dataset_export(self, payload: DatasetExportCreate) -> DatasetExport:
        with self.session_factory() as session:
            with session.begin():
                dataset_export = DatasetExport(
                    id=self._next_id(session, DatasetExportModel, "dataset-export"),
                    name=payload.name,
                    status=ExportStatus.ready,
                    reviewed_only=payload.reviewed_only,
                    include_detections=payload.include_detections,
                    include_zone_context=payload.include_zone_context,
                    record_count=0,
                    created_at=datetime.now(UTC),
                )
                records, _ = self._export_records_for_current_reviews(session, dataset_export)
                model = DatasetExportModel(
                    id=dataset_export.id,
                    name=dataset_export.name,
                    status=dataset_export.status.value,
                    reviewed_only=dataset_export.reviewed_only,
                    include_detections=dataset_export.include_detections,
                    include_zone_context=dataset_export.include_zone_context,
                    record_count=len(records),
                    created_at=dataset_export.created_at,
                )
                session.add(model)
                session.flush()
                return _dataset_export_from_model(model)

    def build_dataset_manifest(self, export_id: str) -> DatasetExportManifest | None:
        with self.session_factory() as session:
            dataset_export = session.get(DatasetExportModel, export_id)
            if dataset_export is None:
                return None

            return self._build_dataset_manifest_for_export(
                session,
                _dataset_export_from_model(dataset_export),
            )

    def analytics_summary(self) -> AnalyticsSummary:
        with self.session_factory() as session:
            return self._analytics_summary(session)

    def build_analytics_summary(self) -> AnalyticsSummary:
        return self.analytics_summary()

    def dataset_coverage_summary(self) -> DatasetCoverageSummary:
        with self.session_factory() as session:
            return self._dataset_coverage_summary(session)

    def dataset_quality_summary(self) -> DatasetQualitySummary:
        with self.session_factory() as session:
            return self._dataset_quality_summary(session)

    def classifier_readiness_report(self) -> ClassifierReadinessReport:
        with self.session_factory() as session:
            return self._classifier_readiness_report(session)

    def build_classifier_training_manifest(self) -> ClassifierTrainingManifestResponse:
        with self.session_factory() as session:
            return self._classifier_training_manifest(session)

    def create_classifier_manifest_export(
        self,
        payload: ClassifierManifestFileExportRequest,
    ) -> ClassifierManifestFileExportResponse:
        with self.session_factory() as session:
            manifest = self._classifier_training_manifest(session)

        return self._write_classifier_manifest_export(payload, manifest)

    def visit_is_dataset_ready(self, visit: Visit) -> bool:
        with self.session_factory() as session:
            return self._visit_is_dataset_ready(session, visit)

    def event_is_dataset_ready(self, event: Event) -> bool:
        with self.session_factory() as session:
            return self._event_is_dataset_ready(session, event)

    def review_summary_for_dataset_state(self, dataset_ready: bool) -> str:
        if dataset_ready:
            return "Ready for local dataset export. Corrected label will be used as local dataset truth."

        return "Needs review before export. Detections are evidence, not final truth."

    def dataset_export_detail(self, export_id: str) -> DatasetExportDetail | None:
        dataset_export = self.get_dataset_export(export_id)
        manifest = self.build_dataset_manifest(export_id)
        if dataset_export is None or manifest is None:
            return None
        return DatasetExportDetail(export=dataset_export, manifest=manifest)

    def _resolve_import_stream(
        self,
        session: Session,
        stream_id: str | None,
    ) -> StreamModel:
        if stream_id:
            stream_model = session.get(StreamModel, stream_id)
            if stream_model is None:
                raise ValueError("missing_stream")
            return stream_model

        streams = list(session.scalars(select(StreamModel).order_by(StreamModel.id)).all())
        if len(streams) != 1:
            raise ValueError("stream_required")
        return streams[0]

    def _resolve_source_import_stream(
        self,
        session: Session,
        *,
        source_id: str,
        stream_id: str | None,
    ) -> tuple[StreamModel, str | None]:
        if stream_id:
            stream_model = session.get(StreamModel, stream_id)
            if stream_model is None:
                raise ValueError("missing_stream")
            if stream_model.source_id != source_id:
                raise ValueError("stream_source_mismatch")
            return stream_model, None

        streams = list(
            session.scalars(
                select(StreamModel).where(StreamModel.source_id == source_id).order_by(StreamModel.id)
            ).all()
        )
        if not streams:
            raise ValueError("stream_required")
        return (
            streams[0],
            "No stream was supplied; MockingBird used the first stream for this Source.",
        )

    def _resolve_import_zone(
        self,
        session: Session,
        zone_id: str | None,
        stream_id: str,
    ) -> ZoneModel | None:
        if zone_id is None:
            return None

        zone_model = session.get(ZoneModel, zone_id)
        if zone_model is None:
            raise ValueError("missing_zone")
        if zone_model.stream_id != stream_id:
            raise ValueError("zone_stream_mismatch")
        return zone_model

    def _resolve_source_import_zone(
        self,
        session: Session,
        *,
        zone_id: str | None,
        stream_id: str,
    ) -> ZoneModel | None:
        if zone_id is None:
            return None

        zone_model = session.get(ZoneModel, zone_id)
        if zone_model is None:
            raise ValueError("missing_zone")
        if zone_model.stream_id != stream_id:
            raise ValueError("zone_stream_mismatch")
        if zone_model.zone_type in {ZoneType.privacy.value, ZoneType.ignore.value}:
            raise ValueError("zone_blocked")
        return zone_model

    def _folder_import_duplicate_exists(
        self,
        session: Session,
        *,
        source_id: str,
        relative_source_path: str,
        size_bytes: int | None,
        modified_at: datetime | None,
    ) -> bool:
        size_value = "" if size_bytes is None else str(size_bytes)
        modified_value = "" if modified_at is None else modified_at.isoformat()
        assets = session.scalars(
            select(MediaAssetModel).where(MediaAssetModel.source_id == source_id)
        ).all()
        for asset in assets:
            fields = _folder_import_note_fields(asset.notes)
            if (
                fields.get("provider_key") == "folder_import_future"
                and fields.get("source_id") == source_id
                and fields.get("relative_source_path") == relative_source_path
                and fields.get("size_bytes", "") == size_value
                and fields.get("modified_at", "") == modified_value
            ):
                return True
        return False

    def _taxonomy_label_model_for_input(
        self,
        session: Session,
        input_label: str,
    ) -> TaxonomyLabelModel | None:
        lookup_key = _taxonomy_key(input_label)
        if not lookup_key:
            return None

        labels = session.scalars(select(TaxonomyLabelModel).order_by(TaxonomyLabelModel.id)).all()
        for label in labels:
            taxonomy_label = _taxonomy_label_from_model(label)
            candidates = [
                taxonomy_label.id,
                taxonomy_label.label,
                taxonomy_label.display_name,
                *taxonomy_label.aliases,
            ]
            if lookup_key in {_taxonomy_key(candidate) for candidate in candidates}:
                return label
        return None

    def _normalize_label_from_session(self, session: Session, input_label: str) -> str:
        label_model = self._taxonomy_label_model_for_input(session, input_label)
        if label_model is not None:
            return label_model.label
        return _freeform_label(input_label)

    def _adapter_subject_and_species(
        self,
        session: Session,
        normalized_label: str,
    ) -> tuple[str, str | None]:
        taxonomy_label = self._taxonomy_label_model_for_input(session, normalized_label)
        taxonomy = _taxonomy_label_from_model(taxonomy_label) if taxonomy_label else None
        if taxonomy is not None and taxonomy.category == LabelCategory.bird and taxonomy.is_species:
            return "bird", taxonomy.label
        if normalized_label == "unknown_bird":
            return "unknown_bird", "unknown_bird"
        return normalized_label, None

    def _default_demo_zone(self, session: Session, stream_id: str) -> ZoneModel | None:
        zones = list(
            session.scalars(
                select(ZoneModel).where(ZoneModel.stream_id == stream_id).order_by(ZoneModel.id)
            ).all()
        )
        for zone in zones:
            if zone.is_active and zone.zone_type not in {
                ZoneType.ignore.value,
                ZoneType.privacy.value,
            }:
                return zone
        return zones[0] if zones else None

    def _write_media_file(self, filename: str, content: bytes) -> tuple[str, Path]:
        self.media_root.mkdir(parents=True, exist_ok=True)
        path = self.media_root / filename
        if path.exists():
            name = Path(filename)
            counter = 2
            while True:
                candidate = self.media_root / f"{name.stem}-{counter}{name.suffix}"
                if not candidate.exists():
                    path = candidate
                    break
                counter += 1
        path.write_bytes(content)
        return path.name, path

    def _copy_media_file(self, filename: str, source_path: Path) -> tuple[str, Path]:
        self.media_root.mkdir(parents=True, exist_ok=True)
        path = self.media_root / filename
        if path.exists():
            name = Path(filename)
            counter = 2
            while True:
                candidate = self.media_root / f"{name.stem}-{counter}{name.suffix}"
                if not candidate.exists():
                    path = candidate
                    break
                counter += 1
        shutil.copyfile(source_path, path)
        return path.name, path

    def _external_url_preview_media_notes(
        self,
        *,
        source_id: str,
        stream_id: str,
        fetched_at: datetime,
        content_type: str,
        bytes_written: int,
        url_host: str | None,
        note: str | None,
    ) -> str:
        lines = [
            "Saved explicit external_url still-image preview.",
            "Creates no Events, Visits, ReviewLabels, or truth.",
            "provider_key=external_url",
            f"source_id={source_id}",
            f"stream_id={stream_id}",
            f"fetched_at={fetched_at.isoformat()}",
            f"content_type={content_type}",
            f"bytes_written={bytes_written}",
        ]
        if url_host:
            lines.append(f"url_host={url_host}")
        cleaned_note = _clean_optional_text(note)
        if cleaned_note is not None:
            lines.append(f"note={cleaned_note}")
        return "\n".join(lines)

    def _preview_folder_import_for_path(self, folder: Path) -> FolderImportPreview:
        if not folder.exists():
            raise ValueError("folder_missing")
        if not folder.is_dir():
            raise ValueError("folder_not_directory")

        supported_files: list[FolderImportCandidate] = []
        skipped_files: list[FolderImportSkippedFile] = []

        # Folder import is an explicit, non-recursive local source path.
        for path in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file():
                skipped_files.append(
                    FolderImportSkippedFile(filename=path.name, reason="not_file")
                )
                continue

            media_type_info = _media_type_for_path(path)
            if media_type_info is None:
                skipped_files.append(
                    FolderImportSkippedFile(
                        filename=path.name,
                        reason="unsupported_content_type",
                    )
                )
                continue

            file_size = path.stat().st_size
            if file_size <= 0:
                skipped_files.append(
                    FolderImportSkippedFile(filename=path.name, reason="empty_file")
                )
                continue

            content_type, media_type = media_type_info
            supported_files.append(
                FolderImportCandidate(
                    filename=path.name,
                    path=str(path),
                    content_type=content_type,
                    media_type=media_type,
                    file_size_bytes=file_size,
                )
            )

        return FolderImportPreview(
            folder_path=str(folder),
            supported_files=supported_files,
            skipped_files=skipped_files,
            supported_count=len(supported_files),
            skipped_count=len(skipped_files),
        )

    def _create_detection_proposal_review_records(
        self,
        session: Session,
        *,
        proposal_model: DetectionProposalModel,
        payload: DetectionProposalDecisionCreate,
        created_at: datetime,
    ) -> tuple[Event, Visit]:
        asset_model = session.get(MediaAssetModel, proposal_model.media_asset_id)
        if asset_model is None:
            raise ValueError("missing_media_asset")

        stream_model = session.get(StreamModel, proposal_model.stream_id)
        if stream_model is None:
            raise ValueError("missing_stream")

        zone_model = self._resolve_import_zone(
            session,
            proposal_model.zone_id,
            proposal_model.stream_id,
        )
        event_id = self._next_id(session, EventModel, "event-detection")
        visit_id = self._next_id(session, VisitModel, "visit-detection")
        detection_id = self._next_id(session, DetectionModel, "detection-proposal")
        event_title = (
            payload.event_title.strip()
            if payload.event_title and payload.event_title.strip()
            else f"Detection proposal: {proposal_model.label}"
        )
        subject_label = (
            payload.subject_label.strip()
            if payload.subject_label and payload.subject_label.strip()
            else proposal_model.suggested_subject_label
        )
        species_guess = (
            payload.species_guess.strip()
            if payload.species_guess and payload.species_guess.strip()
            else proposal_model.suggested_species
        )

        event_model = EventModel(
            id=event_id,
            stream_id=stream_model.id,
            title=event_title,
            event_type=proposal_model.suggested_event_type,
            started_at=created_at,
            ended_at=created_at,
            primary_zone_id=zone_model.id if zone_model else None,
            review_status=ReviewStatus.needs_review.value,
        )
        visit_model = VisitModel(
            id=visit_id,
            event_id=event_id,
            subject_label=subject_label,
            species_guess=species_guess,
            confidence=proposal_model.confidence,
            reviewed_label=None,
            review_status=ReviewStatus.needs_review.value,
            representative_media_path=asset_model.local_path,
        )
        detection_model = DetectionModel(
            id=detection_id,
            event_id=event_id,
            label=proposal_model.label,
            confidence=proposal_model.confidence,
            zone_id=zone_model.id if zone_model else None,
            bbox_json=proposal_model.bbox_json,
        )
        session.add_all([event_model, visit_model, detection_model])
        session.flush()
        return self._event_from_model(session, event_model), _visit_from_model(visit_model)

    def _create_media_product_records(
        self,
        session: Session,
        *,
        stream_model: StreamModel,
        zone_model: ZoneModel | None,
        content: bytes,
        original_filename: str,
        content_type: str,
        media_type: str,
        title: str | None,
        event_type: str,
        default_title: str,
        subject_label: str,
        species_guess: str | None,
        notes: str | None,
    ) -> tuple[MediaAsset, Event, Visit]:
        media_id = self._next_id(session, MediaAssetModel, "media-asset")
        event_id = self._next_id(session, EventModel, "event-media")
        visit_id = self._next_id(session, VisitModel, "visit-media")
        filename = f"{media_id}-{_safe_filename(original_filename)}"
        filename, local_path = self._write_media_file(filename, content)
        created_at = datetime.now(UTC)

        asset_model = MediaAssetModel(
            id=media_id,
            source_id=stream_model.source_id,
            stream_id=stream_model.id,
            filename=filename,
            content_type=content_type,
            media_type=media_type,
            local_path=str(local_path),
            original_filename=original_filename or filename,
            file_size_bytes=len(content),
            created_at=created_at,
            notes=notes,
        )
        event_model = EventModel(
            id=event_id,
            stream_id=stream_model.id,
            title=title.strip() if title and title.strip() else default_title,
            event_type=event_type,
            started_at=created_at,
            ended_at=created_at,
            primary_zone_id=zone_model.id if zone_model else None,
            review_status=ReviewStatus.needs_review.value,
        )
        visit_model = VisitModel(
            id=visit_id,
            event_id=event_id,
            subject_label=subject_label.strip() or "unknown_animal",
            species_guess=(
                species_guess.strip()
                if species_guess and species_guess.strip()
                else None
            ),
            confidence=None,
            reviewed_label=None,
            review_status=ReviewStatus.needs_review.value,
            representative_media_path=str(local_path),
        )
        session.add_all([asset_model, event_model, visit_model])
        session.flush()

        return (
            _media_asset_from_model(asset_model),
            self._event_from_model(session, event_model),
            _visit_from_model(visit_model),
        )

    def _media_asset_for_path_from_session(
        self,
        session: Session,
        media_path: str | None,
    ) -> MediaAsset | None:
        if media_path is None:
            return None

        asset = session.scalar(
            select(MediaAssetModel).where(MediaAssetModel.local_path == media_path)
        )
        return _media_asset_from_model(asset) if asset else None

    def _zones_for_stream(self, session: Session, stream_id: str) -> list[Zone]:
        zones = session.scalars(
            select(ZoneModel).where(ZoneModel.stream_id == stream_id).order_by(ZoneModel.id)
        ).all()
        return [_zone_from_model(zone) for zone in zones]

    def _visit_models_for_event(self, session: Session, event_id: str) -> list[VisitModel]:
        return list(
            session.scalars(
                select(VisitModel).where(VisitModel.event_id == event_id).order_by(VisitModel.id)
            ).all()
        )

    def _visits_for_event(self, session: Session, event_id: str) -> list[Visit]:
        return [_visit_from_model(visit) for visit in self._visit_models_for_event(session, event_id)]

    def _review_label_models_for_event(
        self,
        session: Session,
        event_id: str,
    ) -> list[ReviewLabelModel]:
        return list(
            session.scalars(
                select(ReviewLabelModel)
                .where(
                    ReviewLabelModel.target_type == "event",
                    ReviewLabelModel.target_id == event_id,
                )
                .order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
            ).all()
        )

    def _review_label_models_for_visit(
        self,
        session: Session,
        visit_id: str,
    ) -> list[ReviewLabelModel]:
        return list(
            session.scalars(
                select(ReviewLabelModel)
                .where(
                    ReviewLabelModel.target_type == "visit",
                    ReviewLabelModel.target_id == visit_id,
                )
                .order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
            ).all()
        )

    def _review_labels_for_event(self, session: Session, event_id: str) -> list[ReviewLabel]:
        return [
            _review_label_from_model(label)
            for label in self._review_label_models_for_event(session, event_id)
        ]

    def _review_labels_for_visit(self, session: Session, visit_id: str) -> list[ReviewLabel]:
        return [
            _review_label_from_model(label)
            for label in self._review_label_models_for_visit(session, visit_id)
        ]

    def _event_from_model(self, session: Session, event: EventModel) -> Event:
        detections = session.scalars(
            select(DetectionModel)
            .where(DetectionModel.event_id == event.id)
            .order_by(DetectionModel.id)
        ).all()
        return Event(
            id=event.id,
            stream_id=event.stream_id,
            title=event.title,
            event_type=event.event_type,
            started_at=_as_utc(event.started_at),
            ended_at=_as_utc(event.ended_at) if event.ended_at else None,
            primary_zone_id=event.primary_zone_id,
            review_status=ReviewStatus(event.review_status),
            detections=[_detection_from_model(detection) for detection in detections],
        )

    def _visit_is_dataset_ready(self, session: Session, visit: Visit) -> bool:
        return visit.review_status == ReviewStatus.reviewed and (
            visit.reviewed_label is not None
            or bool(self._review_label_models_for_visit(session, visit.id))
            or bool(self._review_label_models_for_event(session, visit.event_id))
        )

    def _event_is_dataset_ready(self, session: Session, event: Event) -> bool:
        visits = self._visits_for_event(session, event.id)
        if visits:
            return all(self._visit_is_dataset_ready(session, visit) for visit in visits)

        return event.review_status == ReviewStatus.reviewed and bool(
            self._review_label_models_for_event(session, event.id)
        )

    def _latest_label(self, labels: list[ReviewLabel]) -> str | None:
        if not labels:
            return None
        return max(labels, key=lambda label: label.created_at).label

    def _adapter_evaluation_item(
        self,
        session: Session,
        *,
        proposal_model: DetectionProposalModel,
        adapter: ModelAdapter | None,
    ) -> AdapterEvaluationItem:
        proposal_label = self._normalize_label_from_session(session, proposal_model.label)
        reviewed_label, review_status = self._proposal_review_truth(session, proposal_model)

        if proposal_model.status == DetectionProposalStatus.rejected.value:
            outcome = AdapterEvaluationOutcome.rejected_evidence
            review_status = ReviewStatus.rejected
        elif reviewed_label is None:
            outcome = (
                AdapterEvaluationOutcome.converted_needs_review
                if proposal_model.event_id is not None or proposal_model.visit_id is not None
                else AdapterEvaluationOutcome.awaiting_review
            )
        elif reviewed_label in {"unknown_bird", "unknown_animal"}:
            outcome = AdapterEvaluationOutcome.unknown_reviewed_label
        elif reviewed_label == proposal_label:
            outcome = AdapterEvaluationOutcome.matched_reviewed_truth
        else:
            outcome = AdapterEvaluationOutcome.mismatched_reviewed_truth

        return AdapterEvaluationItem(
            proposal_id=proposal_model.id,
            detection_run_id=proposal_model.run_id,
            adapter_id=adapter.id if adapter else None,
            media_asset_id=proposal_model.media_asset_id,
            event_id=proposal_model.event_id,
            visit_id=proposal_model.visit_id,
            proposal_label=proposal_label,
            proposal_display_name=self._display_name_for_label(session, proposal_label),
            proposal_confidence=proposal_model.confidence,
            reviewed_label=reviewed_label,
            reviewed_display_name=(
                self._display_name_for_label(session, reviewed_label)
                if reviewed_label is not None
                else None
            ),
            review_status=review_status,
            outcome=outcome,
            notes=_adapter_evaluation_note(outcome),
        )

    def _proposal_review_truth(
        self,
        session: Session,
        proposal_model: DetectionProposalModel,
    ) -> tuple[str | None, ReviewStatus]:
        if proposal_model.visit_id is not None:
            visit_model = session.get(VisitModel, proposal_model.visit_id)
            if visit_model is not None:
                visit_status = ReviewStatus(visit_model.review_status)
                visit_label = visit_model.reviewed_label or self._latest_label(
                    self._review_labels_for_visit(session, visit_model.id)
                )
                if visit_status == ReviewStatus.reviewed and visit_label is not None:
                    return self._normalize_label_from_session(session, visit_label), visit_status

                event_model = session.get(EventModel, visit_model.event_id)
                if event_model is not None:
                    event_status = ReviewStatus(event_model.review_status)
                    event_label = self._latest_label(
                        self._review_labels_for_event(session, event_model.id)
                    )
                    if event_status == ReviewStatus.reviewed and event_label is not None:
                        return (
                            self._normalize_label_from_session(session, event_label),
                            event_status,
                        )
                return None, visit_status

        if proposal_model.event_id is not None:
            event_model = session.get(EventModel, proposal_model.event_id)
            if event_model is not None:
                event_status = ReviewStatus(event_model.review_status)
                event_label = self._latest_label(
                    self._review_labels_for_event(session, event_model.id)
                )
                if event_status == ReviewStatus.reviewed and event_label is not None:
                    return self._normalize_label_from_session(session, event_label), event_status
                return None, event_status

        return None, ReviewStatus.needs_review

    def _display_name_for_label(self, session: Session, label: str) -> str:
        taxonomy_label = self._taxonomy_label_model_for_input(session, label)
        if taxonomy_label is not None:
            return _taxonomy_label_from_model(taxonomy_label).display_name
        return _display_name_from_label(label)

    def _zone_context(
        self,
        session: Session,
        zone_id: str | None,
    ) -> tuple[str | None, str | None, ZoneType | None]:
        if zone_id is None:
            return None, None, None

        zone = session.get(ZoneModel, zone_id)
        if zone is None:
            return zone_id, None, None

        zone_schema = _zone_from_model(zone)
        return zone_schema.id, zone_schema.name, zone_schema.zone_type

    def _visit_export_record(
        self,
        session: Session,
        visit: Visit,
        event: Event,
        stream: Stream,
        export: DatasetExport,
    ) -> DatasetExportRecord:
        zone_id, zone_name, zone_type = (
            self._zone_context(session, event.primary_zone_id)
            if export.include_zone_context
            else (None, None, None)
        )
        label = (
            visit.reviewed_label
            or self._latest_label(self._review_labels_for_visit(session, visit.id))
            or self._latest_label(self._review_labels_for_event(session, event.id))
            or visit.species_guess
            or visit.subject_label
        )
        taxonomy_label = self._taxonomy_label_model_for_input(session, label)
        taxonomy = _taxonomy_label_from_model(taxonomy_label) if taxonomy_label else None

        return DatasetExportRecord(
            record_id=f"record-{visit.id}",
            event_id=event.id,
            visit_id=visit.id,
            stream_id=event.stream_id,
            source_id=stream.source_id,
            label=label,
            label_display_name=taxonomy.display_name if taxonomy else None,
            label_category=taxonomy.category if taxonomy else None,
            is_species=taxonomy.is_species if taxonomy else None,
            subject_label=visit.subject_label,
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            reviewed=visit.review_status == ReviewStatus.reviewed,
            dataset_ready=self._visit_is_dataset_ready(session, visit),
            media_path=visit.representative_media_path,
            started_at=event.started_at,
            detections=event.detections if export.include_detections else [],
        )

    def _event_export_record(
        self,
        session: Session,
        event: Event,
        stream: Stream,
        export: DatasetExport,
    ) -> DatasetExportRecord:
        zone_id, zone_name, zone_type = (
            self._zone_context(session, event.primary_zone_id)
            if export.include_zone_context
            else (None, None, None)
        )
        label = self._latest_label(self._review_labels_for_event(session, event.id)) or (
            event.detections[0].label if event.detections else event.event_type
        )
        taxonomy_label = self._taxonomy_label_model_for_input(session, label)
        taxonomy = _taxonomy_label_from_model(taxonomy_label) if taxonomy_label else None

        return DatasetExportRecord(
            record_id=f"record-{event.id}",
            event_id=event.id,
            visit_id=None,
            stream_id=event.stream_id,
            source_id=stream.source_id,
            label=label,
            label_display_name=taxonomy.display_name if taxonomy else None,
            label_category=taxonomy.category if taxonomy else None,
            is_species=taxonomy.is_species if taxonomy else None,
            subject_label=event.event_type,
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            reviewed=event.review_status == ReviewStatus.reviewed,
            dataset_ready=self._event_is_dataset_ready(session, event),
            media_path=None,
            started_at=event.started_at,
            detections=event.detections if export.include_detections else [],
        )

    def _export_records_for_current_reviews(
        self,
        session: Session,
        export: DatasetExport,
    ) -> tuple[list[DatasetExportRecord], Counter[str]]:
        records: list[DatasetExportRecord] = []
        skipped_reasons: Counter[str] = Counter()
        visits = self._visits_for_eventless_query(session)
        event_ids_with_visits = {visit.event_id for visit in visits}

        for visit in visits:
            event_model = session.get(EventModel, visit.event_id)
            if event_model is None:
                skipped_reasons["missing_event"] += 1
                continue

            event = self._event_from_model(session, event_model)
            stream_model = session.get(StreamModel, event.stream_id)
            if stream_model is None:
                skipped_reasons["missing_stream"] += 1
                continue
            stream = _stream_from_model(stream_model)

            dataset_ready = self._visit_is_dataset_ready(session, visit)
            if export.reviewed_only and not dataset_ready:
                skipped_reasons["needs_review"] += 1
                continue

            records.append(self._visit_export_record(session, visit, event, stream, export))

        event_models = session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
        for event_model in event_models:
            if event_model.id in event_ids_with_visits:
                continue

            stream_model = session.get(StreamModel, event_model.stream_id)
            if stream_model is None:
                skipped_reasons["missing_stream"] += 1
                continue
            stream = _stream_from_model(stream_model)
            event = self._event_from_model(session, event_model)

            dataset_ready = self._event_is_dataset_ready(session, event)
            if export.reviewed_only and not dataset_ready:
                skipped_reasons["needs_review"] += 1
                continue

            records.append(self._event_export_record(session, event, stream, export))

        return records, skipped_reasons

    def _build_dataset_manifest_for_export(
        self,
        session: Session,
        dataset_export: DatasetExport,
    ) -> DatasetExportManifest:
        # Dataset manifests use corrections as truth, detections as evidence,
        # and imported media paths as local references.
        records, skipped_reasons = self._export_records_for_current_reviews(session, dataset_export)
        return DatasetExportManifest(
            export=dataset_export,
            records=records,
            skipped_count=sum(skipped_reasons.values()),
            skipped_reasons=dict(skipped_reasons),
            generated_at=datetime.now(UTC),
        )

    def _review_queue_items(self, session: Session) -> list[ReviewQueueItem]:
        queue: list[ReviewQueueItem] = []
        visits = self._visits_for_eventless_query(session)

        for visit in visits:
            if visit.review_status != ReviewStatus.needs_review:
                continue

            event_model = session.get(EventModel, visit.event_id)
            if event_model is None:
                continue

            event = self._event_from_model(session, event_model)
            queue.append(
                ReviewQueueItem(
                    id=f"review-queue-{visit.id}",
                    item_type="visit",
                    title=f"Review {visit.subject_label} visit",
                    stream_id=event.stream_id,
                    event_id=event.id,
                    visit_id=visit.id,
                    primary_zone_id=event.primary_zone_id,
                    suggested_label=visit.species_guess or visit.subject_label,
                    media_asset=self._media_asset_for_path_from_session(
                        session,
                        visit.representative_media_path,
                    ),
                    review_status=visit.review_status,
                    reason="Confirm or correct the suggested species label.",
                )
            )

        visit_event_ids = {item.event_id for item in queue if item.event_id is not None}
        event_models = session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
        for event_model in event_models:
            event = self._event_from_model(session, event_model)
            if event.review_status != ReviewStatus.needs_review or event.id in visit_event_ids:
                continue

            queue.append(
                ReviewQueueItem(
                    id=f"review-queue-{event.id}",
                    item_type="event",
                    title=event.title,
                    stream_id=event.stream_id,
                    event_id=event.id,
                    visit_id=None,
                    primary_zone_id=event.primary_zone_id,
                    suggested_label=event.detections[0].label if event.detections else None,
                    review_status=event.review_status,
                    reason="Review detected outdoor activity and correct the event meaning.",
                )
            )

        return queue

    def _dataset_quality_summary(self, session: Session) -> DatasetQualitySummary:
        issues: list[DatasetQualityIssue] = []
        export_ready_count = 0
        needs_review_count = 0

        def add_issue(
            *,
            severity: str,
            issue_type: str,
            title: str,
            description: str,
            target_type: str,
            target_id: str,
            suggested_action: str,
            event_id: str | None = None,
            visit_id: str | None = None,
            media_asset_id: str | None = None,
            label: str | None = None,
        ) -> None:
            issues.append(
                DatasetQualityIssue(
                    id=f"quality-{issue_type}-{target_type}-{target_id}",
                    severity=severity,
                    issue_type=issue_type,
                    title=title,
                    description=description,
                    target_type=target_type,
                    target_id=target_id,
                    event_id=event_id,
                    visit_id=visit_id,
                    media_asset_id=media_asset_id,
                    label=label,
                    suggested_action=suggested_action,
                    link_path=f"{target_type}:{target_id}",
                )
            )

        def has_conflicting_corrections(labels: list[ReviewLabelModel]) -> bool:
            normalized_labels = {
                self._normalize_label_from_session(session, label.label)
                for label in labels
            }
            return len(normalized_labels) > 1

        def add_record_issues(
            *,
            target_type: str,
            target_id: str,
            event: Event,
            visit_id: str | None,
            label: str,
            has_review_truth: bool,
            dataset_ready: bool,
            media_path: str | None,
            media_asset_id: str | None,
            review_label_models: list[ReviewLabelModel],
        ) -> None:
            nonlocal export_ready_count
            nonlocal needs_review_count

            normalized_label = self._normalize_label_from_session(session, label)
            taxonomy_label = self._taxonomy_label_model_for_input(session, normalized_label)

            if dataset_ready:
                export_ready_count += 1
            else:
                needs_review_count += 1
                add_issue(
                    severity="high",
                    issue_type="needs_review",
                    title="Review needed before export",
                    description=(
                        "This record is not export-ready because corrected labels are not "
                        "available as local dataset truth yet."
                    ),
                    target_type=target_type,
                    target_id=target_id,
                    event_id=event.id,
                    visit_id=visit_id,
                    media_asset_id=media_asset_id,
                    label=normalized_label,
                    suggested_action="Open the Review Queue and save a corrected label.",
                )

            if normalized_label in {"unknown_bird", "unknown_animal"}:
                add_issue(
                    severity="medium",
                    issue_type="unknown_label",
                    title="Unknown label needing review",
                    description=(
                        f"{_display_name_from_label(normalized_label)} is useful as a "
                        "temporary review label, but should be resolved before clean exports."
                    ),
                    target_type=target_type,
                    target_id=target_id,
                    event_id=event.id,
                    visit_id=visit_id,
                    media_asset_id=media_asset_id,
                    label=normalized_label,
                    suggested_action="Resolve the unknown label to a reviewed species or activity label.",
                )

            if has_review_truth and taxonomy_label is None:
                add_issue(
                    severity="low",
                    issue_type="freeform_label",
                    title="Freeform label outside taxonomy",
                    description=(
                        "This corrected label is allowed, but it is not part of the current "
                        "taxonomy and may need cleanup before future model work."
                    ),
                    target_type=target_type,
                    target_id=target_id,
                    event_id=event.id,
                    visit_id=visit_id,
                    media_asset_id=media_asset_id,
                    label=normalized_label,
                    suggested_action="Review whether this should map to an existing taxonomy label.",
                )

            if normalized_label == "false_positive":
                add_issue(
                    severity="low",
                    issue_type="false_positive",
                    title="False positive record",
                    description=(
                        "False positives are useful cleanup signals, but they should not be "
                        "treated as species truth."
                    ),
                    target_type=target_type,
                    target_id=target_id,
                    event_id=event.id,
                    visit_id=visit_id,
                    media_asset_id=media_asset_id,
                    label=normalized_label,
                    suggested_action="Keep as cleanup evidence or exclude from species-focused exports.",
                )

            zone_missing = event.primary_zone_id is None or session.get(ZoneModel, event.primary_zone_id) is None
            if dataset_ready and zone_missing:
                add_issue(
                    severity="medium",
                    issue_type="missing_zone",
                    title="Export-ready record missing zone context",
                    description=(
                        "This reviewed record can export, but zone context would make the "
                        "dataset easier to audit and compare."
                    ),
                    target_type=target_type,
                    target_id=target_id,
                    event_id=event.id,
                    visit_id=visit_id,
                    media_asset_id=media_asset_id,
                    label=normalized_label,
                    suggested_action="Add or choose zone context for future records when possible.",
                )

            imported_media_missing = (
                dataset_ready
                and media_path is not None
                and not media_path.startswith("demo://")
                and media_asset_id is None
            )
            if imported_media_missing:
                add_issue(
                    severity="medium",
                    issue_type="missing_media",
                    title="Reviewed record missing local media reference",
                    description=(
                        "This record looks like imported media, but the local media reference "
                        "is not attached to a media asset."
                    ),
                    target_type=target_type,
                    target_id=target_id,
                    event_id=event.id,
                    visit_id=visit_id,
                    media_asset_id=None,
                    label=normalized_label,
                    suggested_action="Recheck the local media reference before relying on this export record.",
                )

            if has_conflicting_corrections(review_label_models):
                add_issue(
                    severity="medium",
                    issue_type="conflicting_corrections",
                    title="Conflicting corrections",
                    description=(
                        "This target has multiple different correction labels. The latest "
                        "label is used as truth, but cleanup will make the dataset easier to trust."
                    ),
                    target_type=target_type,
                    target_id=target_id,
                    event_id=event.id,
                    visit_id=visit_id,
                    media_asset_id=media_asset_id,
                    label=normalized_label,
                    suggested_action="Review correction history and keep the intended final label.",
                )

        visits = self._visits_for_eventless_query(session)
        event_ids_with_visits = {visit.event_id for visit in visits}

        for visit in visits:
            event_model = session.get(EventModel, visit.event_id)
            if event_model is None or session.get(StreamModel, event_model.stream_id) is None:
                continue

            event = self._event_from_model(session, event_model)
            visit_labels = self._review_label_models_for_visit(session, visit.id)
            event_labels = self._review_label_models_for_event(session, event.id)
            label = (
                visit.reviewed_label
                or self._latest_label([_review_label_from_model(label) for label in visit_labels])
                or self._latest_label([_review_label_from_model(label) for label in event_labels])
                or visit.species_guess
                or visit.subject_label
            )
            media_asset = self._media_asset_for_path_from_session(
                session,
                visit.representative_media_path,
            )
            add_record_issues(
                target_type="visit",
                target_id=visit.id,
                event=event,
                visit_id=visit.id,
                label=label,
                has_review_truth=bool(visit.reviewed_label or visit_labels or event_labels),
                dataset_ready=self._visit_is_dataset_ready(session, visit),
                media_path=visit.representative_media_path,
                media_asset_id=media_asset.id if media_asset else None,
                review_label_models=visit_labels,
            )

        event_models = session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
        for event_model in event_models:
            if event_model.id in event_ids_with_visits:
                continue
            if session.get(StreamModel, event_model.stream_id) is None:
                continue

            event = self._event_from_model(session, event_model)
            event_labels = self._review_label_models_for_event(session, event.id)
            label = self._latest_label([_review_label_from_model(label) for label in event_labels]) or (
                event.detections[0].label if event.detections else event.event_type
            )
            add_record_issues(
                target_type="event",
                target_id=event.id,
                event=event,
                visit_id=None,
                label=label,
                has_review_truth=bool(event_labels),
                dataset_ready=self._event_is_dataset_ready(session, event),
                media_path=None,
                media_asset_id=None,
                review_label_models=event_labels,
            )

        severity_counts = Counter(issue.severity for issue in issues)
        type_counts = Counter(issue.issue_type for issue in issues)
        return DatasetQualitySummary(
            issue_count=len(issues),
            high_count=severity_counts["high"],
            medium_count=severity_counts["medium"],
            low_count=severity_counts["low"],
            freeform_label_count=type_counts["freeform_label"],
            unknown_label_count=type_counts["unknown_label"],
            missing_zone_count=type_counts["missing_zone"],
            missing_media_count=type_counts["missing_media"],
            conflicting_correction_count=type_counts["conflicting_corrections"],
            false_positive_count=type_counts["false_positive"],
            export_ready_count=export_ready_count,
            needs_review_count=needs_review_count,
            issues=sorted(issues, key=lambda issue: (issue.severity, issue.issue_type, issue.target_id)),
            generated_at=datetime.now(UTC),
            local_first_note=(
                "Dataset QA uses corrected labels as local dataset truth. Detection and "
                "proposal labels remain evidence until review; QA highlights cleanup targets "
                "for exports and coverage for future model work."
            ),
        )

    def _dataset_coverage_summary(self, session: Session) -> DatasetCoverageSummary:
        coverage: dict[str, _CoverageAccumulator] = {}
        target_species_models = session.scalars(
            select(TaxonomyLabelModel)
            .where(
                TaxonomyLabelModel.category == LabelCategory.bird.value,
                TaxonomyLabelModel.is_species.is_(True),
            )
            .order_by(TaxonomyLabelModel.sort_order, TaxonomyLabelModel.display_name)
        ).all()
        target_species_labels = [label.label for label in target_species_models]
        target_sort_order = {
            label.label: label.sort_order if label.sort_order is not None else 999_999
            for label in target_species_models
        }

        def ensure_coverage(input_label: str) -> _CoverageAccumulator:
            normalized_label = self._normalize_label_from_session(session, input_label)
            if normalized_label in coverage:
                return coverage[normalized_label]

            taxonomy_label = self._taxonomy_label_model_for_input(session, normalized_label)
            if taxonomy_label is not None:
                taxonomy = _taxonomy_label_from_model(taxonomy_label)
                accumulator = _CoverageAccumulator(
                    label=taxonomy.label,
                    display_name=taxonomy.display_name,
                    category=taxonomy.category.value,
                    is_species=taxonomy.is_species,
                )
            else:
                accumulator = _CoverageAccumulator(
                    label=normalized_label,
                    display_name=_display_name_from_label(normalized_label),
                    category="custom",
                    is_species=False,
                )
            coverage[accumulator.label] = accumulator
            return accumulator

        for target in target_species_models:
            ensure_coverage(target.label)

        reviewed_record_count = 0
        export_ready_count = 0
        needs_review_count = 0
        unknown_bird_count = 0
        unknown_animal_count = 0
        false_positive_count = 0

        def add_coverage_record(
            *,
            label: str,
            dataset_ready: bool,
            media_path: str | None,
            seen_at: datetime,
        ) -> None:
            nonlocal reviewed_record_count
            nonlocal export_ready_count
            nonlocal needs_review_count
            nonlocal unknown_bird_count
            nonlocal unknown_animal_count
            nonlocal false_positive_count

            item = ensure_coverage(label)
            if dataset_ready:
                item.reviewed_record_count += 1
                item.export_ready_count += 1
                reviewed_record_count += 1
                export_ready_count += 1
            else:
                item.needs_review_count += 1
                needs_review_count += 1

            if item.label in {"unknown_bird", "unknown_animal"}:
                item.unknown_count += 1
            if item.label == "unknown_bird":
                unknown_bird_count += 1
            elif item.label == "unknown_animal":
                unknown_animal_count += 1
            elif item.label == "false_positive":
                false_positive_count += 1

            if media_path and self._media_asset_for_path_from_session(session, media_path) is not None:
                item.media_asset_count += 1

            seen_at = _as_utc(seen_at)
            item.first_seen_at = (
                seen_at
                if item.first_seen_at is None or seen_at < item.first_seen_at
                else item.first_seen_at
            )
            item.last_seen_at = (
                seen_at
                if item.last_seen_at is None or seen_at > item.last_seen_at
                else item.last_seen_at
            )

        visits = self._visits_for_eventless_query(session)
        event_ids_with_visits = {visit.event_id for visit in visits}

        for visit in visits:
            event_model = session.get(EventModel, visit.event_id)
            if event_model is None or session.get(StreamModel, event_model.stream_id) is None:
                continue

            event = self._event_from_model(session, event_model)
            label = (
                visit.reviewed_label
                or self._latest_label(self._review_labels_for_visit(session, visit.id))
                or self._latest_label(self._review_labels_for_event(session, event.id))
                or visit.species_guess
                or visit.subject_label
            )
            add_coverage_record(
                label=label,
                dataset_ready=self._visit_is_dataset_ready(session, visit),
                media_path=visit.representative_media_path,
                seen_at=event.started_at,
            )

        event_models = session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
        for event_model in event_models:
            if event_model.id in event_ids_with_visits:
                continue
            if session.get(StreamModel, event_model.stream_id) is None:
                continue

            event = self._event_from_model(session, event_model)
            label = self._latest_label(self._review_labels_for_event(session, event.id)) or (
                event.detections[0].label if event.detections else event.event_type
            )
            add_coverage_record(
                label=label,
                dataset_ready=self._event_is_dataset_ready(session, event),
                media_path=None,
                seen_at=event.started_at,
            )

        covered_target_species = [
            label
            for label in target_species_labels
            if coverage[label].reviewed_record_count > 0
        ]
        missing_target_species = [
            label
            for label in target_species_labels
            if coverage[label].reviewed_record_count == 0
        ]
        gaps = [
            DatasetCoverageGap(
                label=label,
                display_name=coverage[label].display_name,
                reason="missing_reviewed_examples",
                target_category=LabelCategory.bird.value,
            )
            for label in missing_target_species
        ]
        if unknown_bird_count > 0:
            gaps.append(
                DatasetCoverageGap(
                    label="unknown_bird",
                    display_name=ensure_coverage("unknown_bird").display_name,
                    reason="unknown_birds_need_review",
                    target_category=LabelCategory.bird.value,
                )
            )
        if unknown_animal_count > 0:
            gaps.append(
                DatasetCoverageGap(
                    label="unknown_animal",
                    display_name=ensure_coverage("unknown_animal").display_name,
                    reason="unknown_animals_need_review",
                    target_category=LabelCategory.unknown.value,
                )
            )

        species = [
            DatasetCoverageSpecies(
                label=item.label,
                display_name=item.display_name,
                category=item.category,
                is_species=item.is_species,
                reviewed_record_count=item.reviewed_record_count,
                export_ready_count=item.export_ready_count,
                needs_review_count=item.needs_review_count,
                unknown_count=item.unknown_count,
                media_asset_count=item.media_asset_count,
                first_seen_at=item.first_seen_at,
                last_seen_at=item.last_seen_at,
            )
            for item in sorted(
                coverage.values(),
                key=lambda item: (
                    0 if item.label in target_sort_order else 1,
                    target_sort_order.get(item.label, 999_999),
                    item.display_name,
                ),
            )
        ]

        return DatasetCoverageSummary(
            reviewed_record_count=reviewed_record_count,
            export_ready_count=export_ready_count,
            needs_review_count=needs_review_count,
            unknown_bird_count=unknown_bird_count,
            unknown_animal_count=unknown_animal_count,
            false_positive_count=false_positive_count,
            reviewed_species_count=sum(
                item.reviewed_record_count for item in coverage.values() if item.is_species
            ),
            target_species_count=len(target_species_labels),
            covered_target_species_count=len(covered_target_species),
            missing_target_species_count=len(missing_target_species),
            species=species,
            gaps=gaps,
            generated_at=datetime.now(UTC),
            local_first_note=(
                "Dataset coverage uses corrected labels as local dataset truth. "
                "Detection and proposal labels remain evidence until review; coverage is "
                "a signal for future model work and does not run training or classification."
            ),
        )

    def _classifier_readiness_report(self, session: Session) -> ClassifierReadinessReport:
        species_examples: dict[str, dict[str, int | list[str]]] = {}
        skipped_reasons: Counter[str] = Counter()
        warnings: list[str] = []
        reviewed_examples = 0
        media_backed_reviewed_examples = 0
        export_ready_examples = 0
        unknown_label_count = 0
        false_positive_count = 0
        out_of_taxonomy_count = 0
        low_example_threshold = 2
        minimum_species_threshold = 2

        target_species_models = session.scalars(
            select(TaxonomyLabelModel)
            .where(
                TaxonomyLabelModel.category == LabelCategory.bird.value,
                TaxonomyLabelModel.is_species.is_(True),
            )
            .order_by(TaxonomyLabelModel.sort_order, TaxonomyLabelModel.display_name)
        ).all()
        target_species_labels = [label.label for label in target_species_models]
        target_sort_order = {
            label.label: label.sort_order if label.sort_order is not None else 999_999
            for label in target_species_models
        }
        media_backed_target_counts: Counter[str] = Counter()

        def latest_label_from_models(labels: list[ReviewLabelModel]) -> str | None:
            return self._latest_label([_review_label_from_model(label) for label in labels])

        def has_conflicting_corrections(labels: list[ReviewLabelModel]) -> bool:
            normalized_labels = {
                self._normalize_label_from_session(session, label.label)
                for label in labels
            }
            return len(normalized_labels) > 1

        def add_skip(reason: str) -> None:
            skipped_reasons[reason] += 1

        def ensure_species_summary(label: str) -> dict[str, int | list[str]]:
            if label not in species_examples:
                species_examples[label] = {
                    "reviewed_examples": 0,
                    "media_backed_examples": 0,
                    "export_ready_examples": 0,
                    "warnings": [],
                }
            return species_examples[label]

        visits = self._visits_for_eventless_query(session)
        for visit in visits:
            event_model = session.get(EventModel, visit.event_id)
            if event_model is None or session.get(StreamModel, event_model.stream_id) is None:
                add_skip("insufficient_metadata")
                continue

            event = self._event_from_model(session, event_model)
            visit_labels = self._review_label_models_for_visit(session, visit.id)
            event_labels = self._review_label_models_for_event(session, event.id)
            label = (
                visit.reviewed_label
                or latest_label_from_models(visit_labels)
                or latest_label_from_models(event_labels)
            )
            dataset_ready = self._visit_is_dataset_ready(session, visit)

            if not dataset_ready:
                add_skip(
                    "unreviewed"
                    if visit.review_status != ReviewStatus.reviewed
                    else "missing_review_label"
                )
                continue

            if label is None:
                add_skip("missing_review_label")
                continue

            normalized_label = self._normalize_label_from_session(session, label)
            taxonomy_label = self._taxonomy_label_model_for_input(session, normalized_label)
            taxonomy = _taxonomy_label_from_model(taxonomy_label) if taxonomy_label else None
            media_asset = self._media_asset_for_path_from_session(
                session,
                visit.representative_media_path,
            )
            has_media_asset = media_asset is not None
            has_conflicts = has_conflicting_corrections(visit_labels) or (
                not visit_labels and has_conflicting_corrections(event_labels)
            )

            reviewed_examples += 1
            if has_media_asset:
                media_backed_reviewed_examples += 1
            else:
                add_skip("missing_media")

            if normalized_label in {"unknown_bird", "unknown_animal"}:
                unknown_label_count += 1
                add_skip("unknown_label")
            if normalized_label == "false_positive":
                false_positive_count += 1
                add_skip("false_positive_policy_excluded")
            if taxonomy is None:
                out_of_taxonomy_count += 1
                add_skip("out_of_taxonomy")
            if has_conflicts:
                add_skip("conflicting_corrections")

            is_known_species = (
                taxonomy is not None
                and taxonomy.category == LabelCategory.bird
                and taxonomy.is_species
            )
            if not is_known_species:
                continue

            species_summary = ensure_species_summary(taxonomy.label)
            species_summary["reviewed_examples"] = int(species_summary["reviewed_examples"]) + 1
            if has_media_asset:
                species_summary["media_backed_examples"] = (
                    int(species_summary["media_backed_examples"]) + 1
                )
                media_backed_target_counts[taxonomy.label] += 1
            if has_media_asset and not has_conflicts:
                species_summary["export_ready_examples"] = (
                    int(species_summary["export_ready_examples"]) + 1
                )
                export_ready_examples += 1

        species: list[ClassifierReadinessSpeciesSummary] = []
        for label, counts in species_examples.items():
            species_warnings = list(counts["warnings"])
            if int(counts["media_backed_examples"]) == 0:
                species_warnings.append("missing_media")
            if int(counts["export_ready_examples"]) < low_example_threshold:
                species_warnings.append("low_example_count")
            species.append(
                ClassifierReadinessSpeciesSummary(
                    label=label,
                    reviewed_examples=int(counts["reviewed_examples"]),
                    media_backed_examples=int(counts["media_backed_examples"]),
                    export_ready_examples=int(counts["export_ready_examples"]),
                    warnings=species_warnings,
                )
            )

        species.sort(
            key=lambda item: (
                target_sort_order.get(item.label, 999_999),
                _display_name_from_label(item.label),
            )
        )
        missing_target_labels = [
            label for label in target_species_labels if media_backed_target_counts[label] == 0
        ]

        covered_species_count = sum(
            1 for item in species if item.media_backed_examples > 0
        )
        if media_backed_reviewed_examples == 0:
            warnings.append(
                "No reviewed media-backed examples are ready for classifier manifest export."
            )
        if covered_species_count < minimum_species_threshold:
            warnings.append("Fewer than 2 taxonomy species have media-backed reviewed examples.")
        if any("low_example_count" in item.warnings for item in species):
            warnings.append("Some species have fewer than 2 media-backed reviewed examples.")
        if unknown_label_count > 0:
            warnings.append("Unknown labels need review before classifier export.")
        if false_positive_count > 0:
            warnings.append("False-positive labels are excluded from species classifier export.")
        if out_of_taxonomy_count > 0:
            warnings.append("Reviewed labels outside taxonomy need cleanup before classifier export.")
        if skipped_reasons["missing_media"] > 0:
            warnings.append("Some reviewed visits are missing MediaAsset-backed media references.")
        if skipped_reasons["conflicting_corrections"] > 0:
            warnings.append("Conflicting corrections should be cleaned before classifier export.")

        ready_for_manifest_export = export_ready_examples > 0
        if not ready_for_manifest_export:
            recommended_next_step = (
                "Review and correct media-backed visits with taxonomy species labels before "
                "classifier manifest export."
            )
        elif warnings:
            recommended_next_step = (
                "Safe next step: keep cleaning readiness warnings while implementing the "
                "manifest export foundation without training or model runtime."
            )
        else:
            recommended_next_step = (
                "Ready to implement classifier training manifest export foundation using "
                "reviewed correction truth only."
            )

        return ClassifierReadinessReport(
            ready_for_manifest_export=ready_for_manifest_export,
            reviewed_examples=reviewed_examples,
            media_backed_reviewed_examples=media_backed_reviewed_examples,
            export_ready_examples=export_ready_examples,
            species=species,
            missing_target_labels=missing_target_labels,
            unknown_label_count=unknown_label_count,
            false_positive_count=false_positive_count,
            out_of_taxonomy_count=out_of_taxonomy_count,
            skipped=[
                ClassifierReadinessSkipSummary(reason=reason, count=count)
                for reason, count in sorted(skipped_reasons.items())
            ],
            warnings=warnings,
            recommended_next_step=recommended_next_step,
        )

    def _classifier_training_manifest(
        self,
        session: Session,
    ) -> ClassifierTrainingManifestResponse:
        target_species_models = session.scalars(
            select(TaxonomyLabelModel)
            .where(
                TaxonomyLabelModel.category == LabelCategory.bird.value,
                TaxonomyLabelModel.is_species.is_(True),
            )
            .order_by(TaxonomyLabelModel.sort_order, TaxonomyLabelModel.display_name)
        ).all()
        target_species_labels = {label.label for label in target_species_models}
        taxonomy_entries = [
            ClassifierManifestTaxonomyEntry(
                label=label.label,
                taxonomy_id=label.id,
                common_name=label.display_name,
                scientific_name=label.scientific_name,
                aliases=list(_taxonomy_label_from_model(label).aliases),
            )
            for label in target_species_models
        ]
        example_payloads: list[dict[str, Any]] = []
        skipped_records: list[ClassifierManifestSkippedRecord] = []

        def latest_label_model(labels: list[ReviewLabelModel]) -> ReviewLabelModel | None:
            if not labels:
                return None
            return max(labels, key=lambda label: (_as_utc(label.created_at), label.id))

        def has_conflicting_corrections(labels: list[ReviewLabelModel]) -> bool:
            normalized_labels = {
                self._normalize_label_from_session(session, label.label)
                for label in labels
            }
            return len(normalized_labels) > 1

        def add_skipped(
            *,
            visit: Visit,
            event_id: str | None,
            media_asset_id: str | None,
            label: str | None,
            reason: str,
            detail: str | None = None,
        ) -> None:
            skipped_records.append(
                ClassifierManifestSkippedRecord(
                    record_id=f"record-{visit.id}",
                    record_type="visit",
                    visit_id=visit.id,
                    event_id=event_id,
                    media_asset_id=media_asset_id,
                    label=label,
                    reason=reason,
                    detail=detail,
                )
            )

        def split_for_example(example_id: str, example_count: int) -> str:
            if example_count < 3:
                return "train"

            bucket = int(hashlib.sha256(example_id.encode("utf-8")).hexdigest()[:8], 16) % 100
            if bucket < 80:
                return "train"
            if bucket < 90:
                return "validation"
            return "test"

        for visit in self._visits_for_eventless_query(session):
            event_model = session.get(EventModel, visit.event_id)
            if event_model is None:
                add_skipped(
                    visit=visit,
                    event_id=visit.event_id,
                    media_asset_id=None,
                    label=visit.reviewed_label or visit.species_guess or visit.subject_label,
                    reason="insufficient_metadata",
                    detail="Visit event metadata is missing.",
                )
                continue

            stream_model = session.get(StreamModel, event_model.stream_id)
            if stream_model is None:
                add_skipped(
                    visit=visit,
                    event_id=event_model.id,
                    media_asset_id=None,
                    label=visit.reviewed_label or visit.species_guess or visit.subject_label,
                    reason="insufficient_metadata",
                    detail="Visit stream metadata is missing.",
                )
                continue

            event = self._event_from_model(session, event_model)
            stream = _stream_from_model(stream_model)
            zone_model = (
                session.get(ZoneModel, event.primary_zone_id)
                if event.primary_zone_id is not None
                else None
            )
            if zone_model is not None and zone_model.zone_type == ZoneType.privacy.value:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=None,
                    label=visit.reviewed_label or visit.species_guess or visit.subject_label,
                    reason="privacy_zone",
                    detail="Privacy zone visits are excluded from classifier manifests.",
                )
                continue
            if zone_model is not None and zone_model.zone_type == ZoneType.ignore.value:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=None,
                    label=visit.reviewed_label or visit.species_guess or visit.subject_label,
                    reason="ignore_zone",
                    detail="Ignore zone visits are excluded from classifier manifests.",
                )
                continue

            visit_labels = self._review_label_models_for_visit(session, visit.id)
            event_labels = self._review_label_models_for_event(session, event.id)
            review_label_model = latest_label_model(visit_labels) or latest_label_model(event_labels)
            label = visit.reviewed_label or (
                review_label_model.label if review_label_model is not None else None
            )
            fallback_label = label or visit.species_guess or visit.subject_label
            dataset_ready = self._visit_is_dataset_ready(session, visit)

            if not dataset_ready:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=None,
                    label=fallback_label,
                    reason=(
                        "unreviewed"
                        if visit.review_status != ReviewStatus.reviewed
                        else "missing_review_label"
                    ),
                    detail="Only reviewed correction truth can enter classifier manifests.",
                )
                continue

            if label is None:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=None,
                    label=fallback_label,
                    reason="missing_review_label",
                    detail="Reviewed visit has no correction label.",
                )
                continue

            normalized_label = self._normalize_label_from_session(session, label)
            has_conflicts = has_conflicting_corrections(visit_labels) or (
                not visit_labels and has_conflicting_corrections(event_labels)
            )
            if has_conflicts:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=None,
                    label=normalized_label,
                    reason="conflicting_corrections",
                    detail="Multiple correction labels exist for this reviewed visit.",
                )
                continue
            if normalized_label in {"unknown_bird", "unknown_animal"}:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=None,
                    label=normalized_label,
                    reason="unknown_label",
                    detail="Unknown reviewed labels are cleanup targets, not species examples.",
                )
                continue
            if normalized_label == "false_positive":
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=None,
                    label=normalized_label,
                    reason="false_positive_policy_excluded",
                    detail="False positives are excluded until a negative training policy exists.",
                )
                continue

            media_asset = self._media_asset_for_path_from_session(
                session,
                visit.representative_media_path,
            )
            if media_asset is None:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=None,
                    label=normalized_label,
                    reason="missing_media",
                    detail="Visit has no existing MediaAsset-backed local media reference.",
                )
                continue
            if media_asset.media_type != "image":
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=media_asset.id,
                    label=normalized_label,
                    reason="unsupported_media_type",
                    detail="Initial classifier manifests include imported image media only.",
                )
                continue
            if media_asset.stream_id != stream.id:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=media_asset.id,
                    label=normalized_label,
                    reason="insufficient_metadata",
                    detail="MediaAsset stream does not match the reviewed visit stream.",
                )
                continue

            taxonomy_label_model = self._taxonomy_label_model_for_input(session, normalized_label)
            taxonomy = (
                _taxonomy_label_from_model(taxonomy_label_model)
                if taxonomy_label_model
                else None
            )
            is_target_species = (
                taxonomy is not None
                and taxonomy.label in target_species_labels
                and taxonomy.category == LabelCategory.bird
                and taxonomy.is_species
            )
            if not is_target_species:
                add_skipped(
                    visit=visit,
                    event_id=event.id,
                    media_asset_id=media_asset.id,
                    label=normalized_label,
                    reason="out_of_taxonomy",
                    detail="Reviewed label is not a target bird species taxonomy label.",
                )
                continue

            example_id = f"classifier-example-{visit.id}"
            example_payloads.append(
                {
                    "example_id": example_id,
                    "visit_id": visit.id,
                    "event_id": event.id,
                    "media_asset_id": media_asset.id,
                    "source_id": media_asset.source_id or stream.source_id,
                    "stream_id": stream.id,
                    "zone_id": event.primary_zone_id,
                    "local_media_path": media_asset.local_path,
                    "label": taxonomy.label,
                    "taxonomy_id": taxonomy.id,
                    "common_name": taxonomy.display_name,
                    "scientific_name": taxonomy.scientific_name,
                    "reviewed_label_id": (
                        review_label_model.id if review_label_model is not None else None
                    ),
                    "reviewed_at": (
                        _as_utc(review_label_model.created_at).isoformat()
                        if review_label_model is not None
                        else None
                    ),
                    "created_at": _as_utc(event.started_at).isoformat(),
                    "quality_flags": [],
                    "provenance": {
                        "manifest_source": "classifier_training_manifest_preview",
                        "truth_source": "review_label",
                        "review_target_type": (
                            review_label_model.target_type
                            if review_label_model is not None
                            else "visit"
                        ),
                        "review_target_id": (
                            review_label_model.target_id
                            if review_label_model is not None
                            else visit.id
                        ),
                        "media_reference": "media_asset.local_path",
                        "evidence_only_sources": [
                            "SpeciesSuggestion",
                            "MotionEvidence",
                            "DetectionProposal",
                        ],
                    },
                }
            )

        example_count = len(example_payloads)
        examples = [
            ClassifierManifestExample(
                **payload,
                split=split_for_example(payload["example_id"], example_count),
            )
            for payload in example_payloads
        ]
        label_counts = Counter(example.label for example in examples)
        split_counts = Counter(example.split for example in examples)
        skip_counts = Counter(record.reason for record in skipped_records)
        warnings: list[str] = []

        if example_count == 0:
            warnings.append(
                "No reviewed media-backed bird species examples are ready for manifest export."
            )
        elif example_count < 3:
            warnings.append("Small manifest preview uses train split only until more examples exist.")
        elif {"train", "validation", "test"} - set(split_counts):
            warnings.append("Split coverage is limited; add more reviewed examples before training.")
        if skip_counts["missing_media"] > 0:
            warnings.append("Some reviewed visits are missing MediaAsset-backed media references.")
        if skip_counts["unknown_label"] > 0:
            warnings.append("Unknown labels need correction before classifier training.")
        if skip_counts["false_positive_policy_excluded"] > 0:
            warnings.append("False positives are excluded until negative training policy exists.")
        if skip_counts["out_of_taxonomy"] > 0:
            warnings.append("Some reviewed labels are outside target bird species taxonomy.")
        if skip_counts["conflicting_corrections"] > 0:
            warnings.append("Conflicting corrections should be cleaned before classifier export.")

        summary = ClassifierManifestSummary(
            examples=example_count,
            skipped=len(skipped_records),
            labels=dict(sorted(label_counts.items())),
            splits=dict(sorted(split_counts.items())),
            warnings=warnings,
        )

        return ClassifierTrainingManifestResponse(
            manifest_version="classifier-training-preview-v1",
            generated_at=datetime.now(UTC).isoformat(),
            examples=examples,
            skipped_records=skipped_records,
            taxonomy=taxonomy_entries,
            summary=summary,
            warnings=warnings,
        )

    def _write_classifier_manifest_export(
        self,
        payload: ClassifierManifestFileExportRequest,
        manifest: ClassifierTrainingManifestResponse,
    ) -> ClassifierManifestFileExportResponse:
        if payload.media_policy == "copy_media" and not payload.dry_run:
            raise ValueError("copy_media export is dry-run only in this phase.")

        created_at = datetime.now(UTC).isoformat()
        export_id = self._classifier_manifest_export_id(payload.output_name)
        file_names = self._classifier_manifest_export_file_names(payload)
        planned_media_files: list[ClassifierManifestPlannedMediaFile] = []
        skipped_media: list[ClassifierManifestSkippedMediaRecord] = []
        total_planned_media_bytes: int | None = None

        if payload.media_policy == "copy_media":
            (
                planned_media_files,
                skipped_media,
                total_planned_media_bytes,
            ) = self._plan_classifier_manifest_media_copy(manifest)

        if payload.dry_run:
            return ClassifierManifestFileExportResponse(
                export_id=export_id,
                output_directory=None,
                files=[
                    ClassifierManifestExportFile(
                        name=name,
                        relative_path=name,
                        content_type=CLASSIFIER_MANIFEST_EXPORT_CONTENT_TYPES[name],
                        size_bytes=None,
                    )
                    for name in file_names
                ],
                examples=len(manifest.examples),
                skipped=len(manifest.skipped_records),
                warnings=manifest.warnings,
                created_at=created_at,
                dry_run=True,
                media_policy=payload.media_policy,
                planned_media_files=planned_media_files,
                skipped_media=skipped_media,
                total_planned_media_bytes=total_planned_media_bytes,
            )

        export_root = self.classifier_manifest_export_root.resolve(strict=False)
        export_root.mkdir(parents=True, exist_ok=True)
        output_dir = self._classifier_manifest_output_dir(export_root, export_id)
        temporary_dir = self._classifier_manifest_output_dir(
            export_root,
            f".{export_id}.tmp",
        )
        if output_dir.exists() or temporary_dir.exists():
            raise ValueError("classifier manifest export directory already exists")

        temporary_dir.mkdir()
        try:
            self._write_classifier_manifest_files(
                temporary_dir,
                file_names,
                payload,
                manifest,
                export_id,
                created_at,
            )
            temporary_dir.rename(output_dir)
        except Exception:
            shutil.rmtree(temporary_dir, ignore_errors=True)
            raise

        return ClassifierManifestFileExportResponse(
            export_id=export_id,
            output_directory=str(output_dir),
            files=[
                ClassifierManifestExportFile(
                    name=name,
                    relative_path=name,
                    content_type=CLASSIFIER_MANIFEST_EXPORT_CONTENT_TYPES[name],
                    size_bytes=(output_dir / name).stat().st_size,
                )
                for name in file_names
            ],
            examples=len(manifest.examples),
            skipped=len(manifest.skipped_records),
            warnings=manifest.warnings,
            created_at=created_at,
            dry_run=False,
            media_policy=payload.media_policy,
            planned_media_files=[],
            skipped_media=[],
            total_planned_media_bytes=None,
        )

    def _classifier_manifest_export_id(self, output_name: str | None) -> str:
        base_name = output_name or "classifier-manifest"
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{base_name}-{timestamp}-{uuid.uuid4().hex[:8]}"

    def _classifier_manifest_output_dir(self, export_root: Path, directory_name: str) -> Path:
        output_dir = (export_root / directory_name).resolve(strict=False)
        if not output_dir.is_relative_to(export_root):
            raise ValueError("classifier manifest export path must stay under the export root")
        return output_dir

    def _classifier_manifest_export_file_names(
        self,
        payload: ClassifierManifestFileExportRequest,
    ) -> list[str]:
        file_names = [
            "manifest.jsonl",
            "taxonomy.json",
            "skipped_records.jsonl",
        ]
        if payload.include_summary:
            file_names.append("summary.json")
        if payload.include_csv:
            file_names.append("manifest.csv")
        return file_names

    def _plan_classifier_manifest_media_copy(
        self,
        manifest: ClassifierTrainingManifestResponse,
    ) -> tuple[
        list[ClassifierManifestPlannedMediaFile],
        list[ClassifierManifestSkippedMediaRecord],
        int | None,
    ]:
        planned_media_files: list[ClassifierManifestPlannedMediaFile] = []
        skipped_media: list[ClassifierManifestSkippedMediaRecord] = []

        for example in manifest.examples:
            source_path = example.local_media_path
            if not source_path:
                skipped_media.append(
                    ClassifierManifestSkippedMediaRecord(
                        example_id=example.example_id,
                        media_asset_id=example.media_asset_id,
                        source_path=None,
                        reason="media_source_missing",
                        detail="Manifest example has no local media path to copy.",
                    )
                )
                continue

            path = Path(source_path)
            suffix = path.suffix.lower()
            if suffix not in CLASSIFIER_MANIFEST_COPY_IMAGE_EXTENSIONS:
                skipped_media.append(
                    ClassifierManifestSkippedMediaRecord(
                        example_id=example.example_id,
                        media_asset_id=example.media_asset_id,
                        source_path=source_path,
                        reason="unsupported_media_type",
                        detail="Media-copy dry-run initially supports image file extensions only.",
                    )
                )
                continue
            if not path.exists() or not path.is_file():
                skipped_media.append(
                    ClassifierManifestSkippedMediaRecord(
                        example_id=example.example_id,
                        media_asset_id=example.media_asset_id,
                        source_path=source_path,
                        reason="stale_media_reference",
                        detail="Local media path does not point to an existing file.",
                    )
                )
                continue

            try:
                size_bytes = path.stat().st_size
            except OSError:
                skipped_media.append(
                    ClassifierManifestSkippedMediaRecord(
                        example_id=example.example_id,
                        media_asset_id=example.media_asset_id,
                        source_path=source_path,
                        reason="stale_media_reference",
                        detail="Local media size could not be read with filesystem metadata.",
                    )
                )
                continue

            planned_media_files.append(
                ClassifierManifestPlannedMediaFile(
                    example_id=example.example_id,
                    media_asset_id=example.media_asset_id,
                    source_path=source_path,
                    planned_relative_path=(
                        f"media/{self._classifier_manifest_safe_media_stem(example.example_id)}"
                        f"{suffix}"
                    ),
                    size_bytes=size_bytes,
                    reason=None,
                )
            )

        total_planned_media_bytes = sum(
            planned.size_bytes or 0 for planned in planned_media_files
        )
        return planned_media_files, skipped_media, total_planned_media_bytes

    def _classifier_manifest_safe_media_stem(self, example_id: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", example_id).strip(".-")
        return safe or "classifier-example"

    def _write_classifier_manifest_files(
        self,
        output_dir: Path,
        file_names: list[str],
        payload: ClassifierManifestFileExportRequest,
        manifest: ClassifierTrainingManifestResponse,
        export_id: str,
        created_at: str,
    ) -> None:
        if "manifest.jsonl" in file_names:
            self._write_jsonl(
                output_dir / "manifest.jsonl",
                [example.model_dump(mode="json") for example in manifest.examples],
            )
        if "taxonomy.json" in file_names:
            self._write_json(
                output_dir / "taxonomy.json",
                [entry.model_dump(mode="json") for entry in manifest.taxonomy],
            )
        if "skipped_records.jsonl" in file_names:
            self._write_jsonl(
                output_dir / "skipped_records.jsonl",
                [record.model_dump(mode="json") for record in manifest.skipped_records],
            )
        if "summary.json" in file_names:
            self._write_json(
                output_dir / "summary.json",
                self._classifier_manifest_export_summary(
                    payload,
                    manifest,
                    export_id,
                    created_at,
                    file_names,
                ),
            )
        if "manifest.csv" in file_names:
            self._write_classifier_manifest_csv(output_dir / "manifest.csv", manifest)

    def _classifier_manifest_export_summary(
        self,
        payload: ClassifierManifestFileExportRequest,
        manifest: ClassifierTrainingManifestResponse,
        export_id: str,
        created_at: str,
        file_names: list[str],
    ) -> dict[str, Any]:
        return {
            "export_id": export_id,
            "created_at": created_at,
            "manifest_version": manifest.manifest_version,
            "manifest_generated_at": manifest.generated_at,
            "media_policy": payload.media_policy,
            "split_seed": payload.split_seed,
            "dry_run": payload.dry_run,
            "include_csv": payload.include_csv,
            "include_summary": payload.include_summary,
            "examples": len(manifest.examples),
            "skipped": len(manifest.skipped_records),
            "skipped_reasons": dict(
                sorted(Counter(record.reason for record in manifest.skipped_records).items())
            ),
            "labels": manifest.summary.labels,
            "splits": manifest.summary.splits,
            "warnings": manifest.warnings,
            "files": file_names,
        }

    def _write_jsonl(self, path: Path, records: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True))
                handle.write("\n")

    def _write_json(self, path: Path, payload: Any) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def _write_classifier_manifest_csv(
        self,
        path: Path,
        manifest: ClassifierTrainingManifestResponse,
    ) -> None:
        fieldnames = [
            "example_id",
            "visit_id",
            "event_id",
            "media_asset_id",
            "source_id",
            "stream_id",
            "zone_id",
            "local_media_path",
            "label",
            "taxonomy_id",
            "common_name",
            "scientific_name",
            "reviewed_label_id",
            "reviewed_at",
            "created_at",
            "split",
            "quality_flags",
            "provenance",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for example in manifest.examples:
                row = example.model_dump(mode="json")
                row["quality_flags"] = json.dumps(row["quality_flags"], sort_keys=True)
                row["provenance"] = json.dumps(row["provenance"], sort_keys=True)
                writer.writerow({field: row.get(field) for field in fieldnames})

    def _analytics_summary(self, session: Session) -> AnalyticsSummary:
        events = [
            self._event_from_model(session, event)
            for event in session.scalars(select(EventModel).order_by(EventModel.started_at)).all()
        ]
        visits = self._visits_for_eventless_query(session)
        review_labels = self.list_review_labels_from_session(session)

        needs_review_count = sum(
            event.review_status == ReviewStatus.needs_review for event in events
        ) + sum(visit.review_status == ReviewStatus.needs_review for visit in visits)

        species_counts: Counter[str] = Counter()
        for visit in visits:
            label = visit.reviewed_label or visit.species_guess or visit.subject_label
            species_counts[self._normalize_label_from_session(session, label)] += 1

        visit_event_ids = {visit.event_id for visit in visits}
        for label in review_labels:
            if label.target_type == "visit":
                continue
            if label.target_type == "event" and label.target_id in visit_event_ids:
                continue
            species_counts[self._normalize_label_from_session(session, label.label)] += 1

        label_display_names: dict[str, str] = {}
        label_categories: dict[str, LabelCategory] = {}
        species_label_ids: list[str] = []
        for label in species_counts:
            taxonomy_label = self._taxonomy_label_model_for_input(session, label)
            if taxonomy_label is None:
                continue
            taxonomy = _taxonomy_label_from_model(taxonomy_label)
            label_display_names[label] = taxonomy.display_name
            label_categories[label] = taxonomy.category
            if taxonomy.is_species:
                species_label_ids.append(label)

        zone_activity_counts: Counter[str] = Counter()
        for event in events:
            if event.primary_zone_id is not None:
                zone_activity_counts[event.primary_zone_id] += 1

        return AnalyticsSummary(
            event_count=len(events),
            visit_count=len(visits),
            needs_review_count=needs_review_count,
            species_counts=dict(species_counts),
            label_display_names=label_display_names,
            label_categories=label_categories,
            species_label_ids=species_label_ids,
            zone_activity_counts=dict(zone_activity_counts),
        )

    def list_review_labels_from_session(self, session: Session) -> list[ReviewLabel]:
        labels = session.scalars(
            select(ReviewLabelModel).order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
        ).all()
        return [_review_label_from_model(label) for label in labels]

    def _visits_for_eventless_query(self, session: Session) -> list[Visit]:
        visits = session.scalars(select(VisitModel).order_by(VisitModel.id)).all()
        return [_visit_from_model(visit) for visit in visits]

    def _next_id(self, session: Session, model: type, prefix: str) -> str:
        count = session.scalar(select(func.count(model.id))) or 0
        candidate_number = count + 1
        while True:
            candidate = f"{prefix}-{candidate_number:03d}"
            if session.get(model, candidate) is None:
                return candidate
            candidate_number += 1


def _source_provider_definition(provider_key: str) -> SourceProviderDefinition | None:
    return next(
        (
            definition
            for definition in SOURCE_PROVIDER_DEFINITIONS
            if definition.provider_key == provider_key
        ),
        None,
    )


def _webhook_payload_validation_response(
    *,
    source_id: str,
    valid: bool,
    candidate: WebhookPayloadCandidate | None,
    skipped_reason: str | None,
    warnings: list[str],
) -> WebhookPayloadValidationResponse:
    return WebhookPayloadValidationResponse(
        source_id=source_id,
        provider_key="webhook_future",
        valid=valid,
        dry_run=True,
        would_create_media_asset=False,
        would_create_motion_evidence=False,
        would_create_event=False,
        would_create_visit=False,
        would_create_review_label=False,
        would_create_species_suggestion=False,
        would_create_detection_proposal=False,
        would_create_truth=False,
        candidate=candidate,
        skipped_reason=skipped_reason,
        warnings=warnings,
    )


def _webhook_candidate_from_summary(
    *,
    source_id: str,
    stream_id: str | None,
    zone_id: str | None,
    summary,
) -> WebhookPayloadCandidate:
    return WebhookPayloadCandidate(
        candidate_type=summary.candidate_type,
        source_id=source_id,
        stream_id=stream_id,
        zone_id=zone_id,
        external_event_id=summary.external_event_id,
        external_label=summary.external_label,
        external_confidence=summary.external_confidence,
        media_reference=summary.media_reference,
        message=summary.message,
        warnings=summary.warnings,
    )


def _webhook_payload_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _webhook_config_value(
    configuration: SourceProviderConfiguration,
    key: str,
) -> str | None:
    value = configuration.safe_config_preview.get(key)
    if value is None or value == "not_configured":
        return None
    return value


def _default_source_provider_key(source: CameraSourceModel) -> str:
    if source.kind == SourceKind.demo.value:
        return "demo"
    if source.kind == SourceKind.manual_upload.value:
        return "manual_media"
    if source.kind == SourceKind.local_folder.value:
        return "folder_import_future"
    if source.kind == SourceKind.rtsp.value:
        return "rtsp_future"
    if source.kind == SourceKind.local_camera.value:
        return "browser_camera_future"
    if source.kind == SourceKind.webhook.value:
        return "webhook_future"
    return "external_url"


def _default_source_provider_config(provider_key: str) -> dict[str, str]:
    if provider_key == "demo":
        return {"demo_seed": "backyard-demo"}
    return {}


def _source_provider_kind(provider_key: str) -> SourceProviderKind:
    if provider_key == "demo":
        return SourceProviderKind.demo
    if provider_key == "manual_media":
        return SourceProviderKind.manual_media
    if provider_key == "external_url":
        return SourceProviderKind.external_url
    return SourceProviderKind.future_adapter


def _sanitize_source_provider_config(
    definition: SourceProviderDefinition,
    config: dict[str, str | None],
) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    fields_by_key = {field.key: field for field in definition.fields}
    for key, value in config.items():
        field = fields_by_key.get(key)
        if field is None or value is None:
            continue
        normalized = value.strip()
        if not normalized:
            continue
        if definition.provider_key == "folder_import_future" and key == "folder_path":
            sanitized[key] = normalized
        else:
            sanitized[key] = "configured" if field.secret else normalized
    return sanitized


def _source_provider_configuration_from_model(
    source: CameraSourceModel,
    model: SourceProviderConfigurationModel | None,
    stream_ids: list[str],
) -> SourceProviderConfiguration:
    provider_key = model.provider_key if model is not None else _default_source_provider_key(source)
    definition = _source_provider_definition(provider_key)
    if definition is None:
        provider_key = _default_source_provider_key(source)
        definition = _source_provider_definition(provider_key)
    assert definition is not None

    if model is None:
        config = _default_source_provider_config(provider_key)
    else:
        config = json.loads(model.config_json)
    return _source_provider_configuration_from_config(
        source_id=source.id,
        definition=definition,
        config=config,
        supports_zone_editing=len(stream_ids) > 0 and definition.supports_zone_editing,
    )


def _source_provider_configuration_from_config(
    *,
    source_id: str,
    definition: SourceProviderDefinition,
    config: dict[str, str],
    supports_zone_editing: bool,
) -> SourceProviderConfiguration:
    configured_fields: list[str] = []
    missing_fields: list[str] = []
    safe_config_preview: dict[str, str] = {}

    for field in definition.fields:
        value = (config.get(field.key) or "").strip()
        if value:
            configured_fields.append(field.key)
            safe_config_preview[field.key] = "configured" if field.secret else value
        else:
            safe_config_preview[field.key] = "not_configured"
            if field.required:
                missing_fields.append(field.key)

    if missing_fields:
        missing_labels = [
            field.label for field in definition.fields if field.key in set(missing_fields)
        ]
        if definition.provider_key == "folder_import_future":
            message = "Folder/trail-cam setup metadata is incomplete."
            setup_hint = "Add folder path metadata before explicit preview/import can run."
        elif definition.provider_key == "webhook_future":
            message = "Webhook setup metadata is incomplete."
            setup_hint = (
                "Add shared secret metadata before future webhook validation or ingest "
                "can be implemented."
            )
        else:
            message = "Provider configuration metadata is incomplete."
            setup_hint = f"Add metadata for: {', '.join(missing_labels)}."
    elif definition.provider_key == "folder_import_future":
        message = (
            "Folder/trail-cam setup metadata is saved. Explicit preview/import is "
            "available, and import creates MediaAssets only."
        )
        setup_hint = (
            "Preview or import folder media explicitly; future handoff is required before "
            "evidence or review."
        )
    elif definition.provider_key == "webhook_future":
        message = (
            "Webhook setup metadata is saved. MockingBird does not accept inbound "
            "webhook payloads yet."
        )
        setup_hint = (
            "Future webhook ingest endpoint implementation is required before payloads "
            "can be received."
        )
    elif definition.status == SourceProviderDefinitionStatus.future_adapter:
        message = (
            "Provider configuration metadata is saved. MockingBird will not connect "
            "to this Source yet."
        )
        setup_hint = "Live playback requires a future provider implementation."
    elif definition.provider_key == "demo":
        message = "Demo provider metadata is available for local stream and zone planning."
        setup_hint = "Zone editing can continue with the demo stream panel."
    elif definition.provider_key == "manual_media":
        message = "Manual media provider metadata is available for explicit local imports."
        setup_hint = (
            "Import media for a related Source/Stream; review and correction create truth."
        )
    elif definition.provider_key == "external_url":
        message = "External URL metadata is available for explicit still-image preview fetch."
        setup_hint = "Fetch a still-image preview explicitly; live playback is not implemented."
    else:
        message = "Provider configuration metadata is saved for this Source."
        setup_hint = "Zone editing can continue while playback remains unavailable."

    return SourceProviderConfiguration(
        source_id=source_id,
        provider_key=definition.provider_key,
        configured_fields=configured_fields,
        missing_fields=missing_fields,
        safe_config_preview=safe_config_preview,
        supports_live_playback=False,
        supports_zone_editing=supports_zone_editing,
        message=message,
        setup_hint=setup_hint,
    )


def _source_setup_review_from_contracts(
    *,
    source: CameraSource,
    configuration: SourceProviderConfiguration,
    connection: SourceConnectionStatus,
    provider_display_name: str,
    definition: SourceProviderDefinition | None,
    streams: list[StreamPlaybackStatus],
) -> SourceSetupReviewResponse:
    missing_labels = _field_labels(definition, configuration.missing_fields)
    stream_reviews = [
        SourceSetupReviewStream(
            stream_id=stream.stream_id,
            display_name=stream.display_title,
            playback_status=stream.status.value,
            playback_kind=stream.playback_kind.value,
            supports_live_playback=stream.supports_live_playback,
            supports_zone_editing=stream.supports_zone_editing,
            message=stream.message,
        )
        for stream in streams
    ]
    supports_live_playback = connection.supports_live_playback or any(
        stream.supports_live_playback for stream in streams
    )
    supports_zone_editing = connection.supports_zone_editing or any(
        stream.supports_zone_editing for stream in streams
    )

    if connection.status in {
        SourceConnectionStatusValue.offline,
        SourceConnectionStatusValue.unavailable,
        SourceConnectionStatusValue.unsupported,
    }:
        readiness_level = "unavailable"
        summary = "Source setup cannot provide playback readiness from the current metadata."
        next_step = connection.setup_hint or "Review source metadata before future provider work."
    elif configuration.provider_key == "demo":
        readiness_level = "demo_ready"
        summary = "Demo setup metadata is ready for local stream, zone, and review workflows."
        next_step = (
            "Draw zones and review the demo flow; real playback still needs future provider work."
        )
    elif configuration.missing_fields:
        readiness_level = "needs_setup"
        summary = "Source setup metadata is incomplete."
        if configuration.provider_key == "webhook_future":
            next_step = "Complete webhook shared secret metadata."
        else:
            next_step = f"Add setup metadata for: {', '.join(missing_labels)}."
    elif configuration.provider_key == "manual_media":
        readiness_level = "metadata_ready"
        summary = (
            "Manual media import is available for this Source. Imported media can create "
            "reviewable Events/Visits; corrections remain the source of truth."
        )
        next_step = "Import media for this Source/Stream, then review and correct before export."
    elif configuration.provider_key == "external_url":
        readiness_level = "metadata_ready"
        summary = (
            "External URL metadata is ready for explicit still-image preview fetch. "
            "Live playback is not implemented."
        )
        next_step = "Fetch still-image preview explicitly; zone editing can continue."
    elif configuration.provider_key == "folder_import_future":
        readiness_level = "future_adapter_required"
        summary = (
            "Folder/trail-cam setup metadata is present. Explicit preview/import is "
            "available, import creates MediaAssets only, and live playback is not "
            "implemented."
        )
        next_step = (
            "Import folder media as MediaAssets explicitly; future evidence handoff is "
            "required before review."
        )
    elif configuration.provider_key == "webhook_future":
        readiness_level = "future_adapter_required"
        summary = (
            "Webhook metadata is present, but MockingBird does not ingest webhook "
            "payloads yet."
        )
        next_step = (
            "Future webhook ingest endpoint implementation required before receiving "
            "payloads."
        )
    elif connection.provider_kind == SourceProviderKind.future_adapter or (
        definition is not None
        and definition.status == SourceProviderDefinitionStatus.future_adapter
    ):
        readiness_level = "future_adapter_required"
        summary = "Setup metadata is present, but live playback still needs provider work."
        next_step = "Future provider implementation required before live playback is available."
    else:
        readiness_level = "future_adapter_required"
        summary = "Setup metadata is present, but live playback is not implemented yet."
        next_step = "Live playback is not implemented for this provider yet."

    warnings: list[str] = []
    if configuration.missing_fields:
        warnings.append(f"Missing setup metadata: {', '.join(missing_labels)}.")
    if configuration.provider_key == "folder_import_future":
        warnings.append("Folder import creates MediaAssets only; evidence handoff is future.")
        warnings.append("Live playback is not expected for this provider.")
    elif configuration.provider_key == "webhook_future":
        warnings.append("No webhook ingest endpoint exists yet; no payloads are accepted as records.")
        warnings.append("Webhook metadata creates no media, evidence, Events/Visits, or truth.")
        warnings.append("Live playback is not expected for this provider.")
    elif not supports_live_playback and configuration.provider_key != "manual_media":
        warnings.append("Live playback is not implemented for this provider yet.")
    if not supports_zone_editing:
        warnings.append("No related stream panel is available for zone editing yet.")

    playback_message = (
        "Live playback is not expected for this provider."
        if configuration.provider_key in {"manual_media", "folder_import_future", "webhook_future"}
        else (
            "Live playback is available."
            if supports_live_playback
            else "Live playback is not implemented for this provider yet."
        )
    )
    workflow_step = (
        SourceSetupReviewStep(
            key="manual_media_import",
            label="Manual media import",
            status="available" if not configuration.missing_fields else "warning",
            message=(
                "Manual media import can create reviewable Events/Visits; "
                "corrections remain truth."
            ),
        )
        if configuration.provider_key == "manual_media"
        else SourceSetupReviewStep(
            key="external_url_preview",
            label="Still-image preview",
            status="available" if not configuration.missing_fields else "warning",
            message=(
                "Explicit preview fetch is available; it is not saved and creates no truth."
            ),
        )
        if configuration.provider_key == "external_url"
        else SourceSetupReviewStep(
            key="folder_import_preview",
            label="Folder import preview",
            status="available" if not configuration.missing_fields else "warning",
            message=(
                "Explicit preview and MediaAsset-only import are available; neither creates "
                "evidence, Events/Visits, or truth."
            ),
        )
        if configuration.provider_key == "folder_import_future"
        else SourceSetupReviewStep(
            key="webhook_future_ingest",
            label="Webhook ingest",
            status="future",
            message=(
                "Configuration stores metadata only; no webhook ingest endpoint exists, "
                "no payloads are accepted as records, and no media, evidence, or truth "
                "is created."
            ),
        )
        if configuration.provider_key == "webhook_future"
        else SourceSetupReviewStep(
            key="future_provider",
            label="Future provider work",
            status="future" if not supports_live_playback else "complete",
            message=(
                "Provider metadata remains underneath the product loop."
                if supports_live_playback
                else "Future provider implementation required for real playback."
            ),
        )
    )

    steps = [
        SourceSetupReviewStep(
            key="setup_metadata",
            label="Setup metadata",
            status="missing" if configuration.missing_fields else "complete",
            message=configuration.message,
        ),
        SourceSetupReviewStep(
            key="playback_readiness",
            label="Playback readiness",
            status="available" if supports_live_playback else "future",
            message=playback_message,
        ),
        SourceSetupReviewStep(
            key="zone_editing",
            label="Zone editing",
            status="available" if supports_zone_editing else "unavailable",
            message=(
                "Zone editing can continue with the stream panel."
                if supports_zone_editing
                else "Add a product Stream before zone editing can continue."
            ),
        ),
        workflow_step,
    ]

    return SourceSetupReviewResponse(
        source_id=source.id,
        provider_key=configuration.provider_key,
        provider_display_name=provider_display_name,
        source_status=connection.status.value,
        readiness_level=readiness_level,
        display_title=connection.display_title,
        summary=summary,
        next_step=next_step,
        configured_fields=configuration.configured_fields,
        missing_fields=configuration.missing_fields,
        supports_live_playback=supports_live_playback,
        supports_zone_editing=supports_zone_editing,
        stream_count=len(stream_reviews),
        streams=stream_reviews,
        steps=steps,
        warnings=warnings,
    )


def _field_labels(
    definition: SourceProviderDefinition | None,
    field_keys: list[str],
) -> list[str]:
    if definition is None:
        return field_keys
    fields_by_key = {field.key: field.label for field in definition.fields}
    return [fields_by_key.get(field_key, field_key) for field_key in field_keys]


def _source_provider_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _source_provider_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return parts or None


def _source_folder_import_preview_response(
    *,
    source_id: str,
    preview: folder_import_preview.FolderPreviewResult,
) -> SourceFolderImportPreviewResponse:
    candidates = [
        SourceFolderImportPreviewCandidate(
            relative_path=candidate.relative_path,
            file_name=candidate.file_name,
            extension=candidate.extension,
            size_bytes=candidate.size_bytes,
            modified_at=candidate.modified_at,
            planned_media_kind=candidate.planned_media_kind,
            warnings=candidate.warnings,
        )
        for candidate in preview.candidates
    ]
    skipped = [
        SourceFolderImportPreviewSkipped(
            relative_path=item.relative_path,
            file_name=item.file_name,
            reason=item.reason,
            message=item.message,
        )
        for item in preview.skipped
    ]
    return SourceFolderImportPreviewResponse(
        source_id=source_id,
        provider_key="folder_import_future",
        folder_configured=True,
        recursive=preview.recursive,
        allowed_extensions=preview.allowed_extensions,
        candidates=candidates,
        skipped=skipped,
        total_candidates=len(candidates),
        total_skipped=len(skipped),
        total_known_bytes=preview.total_known_bytes,
        unknown_size_count=preview.unknown_size_count,
        scanned_at=preview.scanned_at,
        dry_run=True,
        creates_media_assets=False,
        creates_events=False,
        creates_visits=False,
        creates_truth=False,
        warnings=preview.warnings,
    )


def _source_from_model(source: CameraSourceModel) -> CameraSource:
    return CameraSource(
        id=source.id,
        name=source.name,
        kind=SourceKind(source.kind),
        status=SourceStatus(source.status),
        description=source.description,
    )


def _model_adapters() -> tuple[ModelAdapter, ...]:
    return (
        *BASE_MODEL_ADAPTERS,
        _local_image_detector_adapter(),
        _megadetector_adapter(),
    )


def _local_image_detector_adapter() -> ModelAdapter:
    status = get_local_detector_status()
    return ModelAdapter(
        id=LOCAL_IMAGE_DETECTOR_ID,
        name="Local Image Detector",
        kind=ModelAdapterKind.object_detector,
        status=ModelAdapterStatus(status.status),
        version="spike-1",
        description=(
            "Local image detector spike for imported images. It creates detection "
            "proposal evidence only and never writes reviewed truth."
        ),
        supported_media_types=sorted(SUPPORTED_IMAGE_CONTENT_TYPES),
        supported_labels=["unknown_animal", "bird", "squirrel", "cat", "person", "vehicle"],
        creates_review_truth=False,
        local_only=True,
        notes=status.detail,
        configuration_status=_model_adapter_configuration_status(
            adapter_id=LOCAL_IMAGE_DETECTOR_ID,
            status=status,
            supported_media_types=sorted(SUPPORTED_IMAGE_CONTENT_TYPES),
            setup_hint=LOCAL_DETECTOR_SETUP_HINT,
        ),
    )


def _megadetector_adapter() -> ModelAdapter:
    status = get_megadetector_status()
    return ModelAdapter(
        id=MEGADETECTOR_ADAPTER_ID,
        name="MegaDetector",
        kind=ModelAdapterKind.object_detector,
        status=ModelAdapterStatus(status.status),
        version="wrapper-1",
        description=(
            "MegaDetector-family local image detector for animal/person/vehicle "
            "proposal evidence. It does not identify species or write reviewed truth."
        ),
        supported_media_types=sorted(SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES),
        supported_labels=MEGADETECTOR_SUPPORTED_LABELS,
        creates_review_truth=False,
        local_only=True,
        notes=status.detail,
        configuration_status=_model_adapter_configuration_status(
            adapter_id=MEGADETECTOR_ADAPTER_ID,
            status=status,
            supported_media_types=sorted(SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES),
            setup_hint=MEGADETECTOR_SETUP_HINT,
        ),
    )


def _model_adapter_configuration_status(
    *,
    adapter_id: str,
    status: LocalDetectorStatus | MegaDetectorStatus,
    supported_media_types: list[str],
    setup_hint: str,
) -> ModelAdapterConfigurationStatus:
    return ModelAdapterConfigurationStatus(
        adapter_id=adapter_id,
        model_path_configured=status.configured,
        labels_path_configured=status.labels_path is not None,
        runtime_available=status.runtime_available,
        supported_media_types=supported_media_types,
        can_run=(
            status.status == ModelAdapterStatus.available.value
            and status.configured
            and status.runtime_available
        ),
        status_reason=status.detail,
        setup_hint=setup_hint,
        creates_review_truth=False,
        local_only=True,
    )


def _model_adapter_by_id(adapter_id: str) -> ModelAdapter | None:
    return next((adapter for adapter in _model_adapters() if adapter.id == adapter_id), None)


def _model_adapter_for_detection_run(run: DetectionRunModel | None) -> ModelAdapter | None:
    if run is None or run.summary is None:
        return None

    summary_key = run.summary.lower()
    return next(
        (
            adapter
            for adapter in _model_adapters()
            if adapter.id.lower() in summary_key or adapter.name.lower() in summary_key
        ),
        None,
    )


def _adapter_evaluation_note(outcome: AdapterEvaluationOutcome) -> str:
    if outcome == AdapterEvaluationOutcome.matched_reviewed_truth:
        return "Proposal evidence agrees with reviewed correction."
    if outcome == AdapterEvaluationOutcome.mismatched_reviewed_truth:
        return "User correction differs from proposal evidence."
    if outcome == AdapterEvaluationOutcome.unknown_reviewed_label:
        return "Reviewed truth is unknown and tracked separately from matches."
    if outcome == AdapterEvaluationOutcome.rejected_evidence:
        return "Proposal was rejected as evidence and does not define truth."
    if outcome == AdapterEvaluationOutcome.converted_needs_review:
        return "Proposal has a review case but still needs corrected truth."
    return "Proposal evidence is awaiting conversion and review."


def _model_readiness_next_step(
    *,
    coverage: DatasetCoverageSummary,
    quality: DatasetQualitySummary,
    taxonomy_count: int,
    adapter_contract_ready: bool,
) -> str:
    if coverage.export_ready_count == 0:
        return "Review and correct local visits/events, then create export-ready dataset records."
    if quality.high_count > 0:
        return "Resolve high-priority dataset QA issues before the first detector spike."
    if taxonomy_count == 0:
        return "Restore taxonomy labels before future detector work."
    if not adapter_contract_ready:
        return "Restore evidence-only adapter guardrails before future detector work."
    if coverage.covered_target_species_count == 0:
        return (
            "Safe next step: try a first detector spike as proposal evidence while "
            "continuing reviewed species coverage work."
        )
    if quality.issue_count > 0:
        return (
            "Safe next step: try a first detector spike as proposal evidence while "
            "continuing dataset QA cleanup."
        )
    return (
        "Ready for first detector spike: keep outputs in DetectionProposal and require "
        "review corrections before exports or analytics treat labels as truth."
    )


def _model_readiness_checklist(
    *,
    coverage: DatasetCoverageSummary,
    quality: DatasetQualitySummary,
    evaluation: AdapterEvaluationSummary,
    taxonomy_count: int,
    adapter_contract_ready: bool,
) -> list[ModelReadinessChecklistItem]:
    checklist: list[ModelReadinessChecklistItem] = []

    def add(
        *,
        item_id: str,
        label: str,
        status: str,
        severity: str,
        description: str,
        suggested_action: str,
        link_path: str | None = None,
    ) -> None:
        checklist.append(
            ModelReadinessChecklistItem(
                id=item_id,
                label=label,
                status=status,
                severity=severity,
                description=description,
                suggested_action=suggested_action,
                link_path=link_path,
            )
        )

    add(
        item_id="reviewed-local-dataset",
        label="Reviewed local dataset",
        status="ready" if coverage.reviewed_record_count > 0 else "blocked",
        severity="low" if coverage.reviewed_record_count > 0 else "high",
        description=(
            f"{coverage.reviewed_record_count} reviewed record"
            f"{'' if coverage.reviewed_record_count == 1 else 's'} are available."
        ),
        suggested_action=(
            "Keep reviewing visits/events so future detector work has local truth."
            if coverage.reviewed_record_count > 0
            else "Open the Review Queue and save corrected labels."
        ),
        link_path="review",
    )
    add(
        item_id="export-ready-records",
        label="Export-ready corrected labels",
        status="ready" if coverage.export_ready_count > 0 else "blocked",
        severity="low" if coverage.export_ready_count > 0 else "high",
        description=(
            f"{coverage.export_ready_count} record"
            f"{'' if coverage.export_ready_count == 1 else 's'} can export with corrected truth."
        ),
        suggested_action=(
            "Use dataset exports to inspect reviewed labels and detection evidence."
            if coverage.export_ready_count > 0
            else "Correct review items until at least one export-ready record exists."
        ),
        link_path="exports",
    )
    add(
        item_id="dataset-qa-high-issues",
        label="Dataset QA high issues",
        status="ready" if quality.high_count == 0 else "blocked",
        severity="low" if quality.high_count == 0 else "high",
        description=(
            f"{quality.high_count} high-priority QA issue"
            f"{'' if quality.high_count == 1 else 's'} remain."
        ),
        suggested_action=(
            "Keep high-priority QA clear before detector spikes."
            if quality.high_count == 0
            else "Resolve high-priority QA issues in the Review Queue."
        ),
        link_path="review",
    )
    add(
        item_id="dataset-qa-cleanup",
        label="Dataset QA cleanup",
        status="ready" if quality.issue_count == 0 else "attention",
        severity="low" if quality.issue_count == 0 else "medium",
        description=(
            f"{quality.issue_count} total QA issue"
            f"{'' if quality.issue_count == 1 else 's'} remain."
        ),
        suggested_action=(
            "QA is clean for the current reviewed local dataset."
            if quality.issue_count == 0
            else "Use QA panels to clean unknown, freeform, missing-zone, or conflict items."
        ),
        link_path="analytics:dataset-quality",
    )
    add(
        item_id="taxonomy-labels",
        label="Taxonomy labels present",
        status="ready" if taxonomy_count > 0 else "blocked",
        severity="low" if taxonomy_count > 0 else "high",
        description=f"{taxonomy_count} review label target{'' if taxonomy_count == 1 else 's'} are available.",
        suggested_action=(
            "Use taxonomy-backed corrections where possible."
            if taxonomy_count > 0
            else "Restore taxonomy labels before detector work."
        ),
    )

    if coverage.target_species_count == 0:
        species_status = "blocked"
        species_severity = "high"
    elif coverage.covered_target_species_count == coverage.target_species_count:
        species_status = "ready"
        species_severity = "low"
    else:
        species_status = "attention"
        species_severity = "medium"
    add(
        item_id="species-coverage",
        label="Coverage for future model work",
        status=species_status,
        severity=species_severity,
        description=(
            f"{coverage.covered_target_species_count}/{coverage.target_species_count} "
            "target species have reviewed records."
        ),
        suggested_action=(
            "Continue reviewing species examples to improve local coverage."
            if species_status != "ready"
            else "Keep coverage current as new reviewed observations arrive."
        ),
        link_path="analytics:dataset-coverage",
    )
    add(
        item_id="adapter-evidence-contract",
        label="Adapter outputs stay evidence-only",
        status="ready" if adapter_contract_ready else "blocked",
        severity="low" if adapter_contract_ready else "high",
        description="Model adapters must create proposals and never write review truth.",
        suggested_action=(
            "Keep future detector outputs below the review/correction boundary."
            if adapter_contract_ready
            else "Fix adapter guardrails before adding detector work."
        ),
        link_path="model-adapters",
    )
    add(
        item_id="adapter-evaluation-signal",
        label="Adapter evidence evaluation",
        status=(
            "ready"
            if evaluation.reviewed_count > 0
            else "attention"
            if evaluation.proposal_count > 0
            else "attention"
        ),
        severity="low" if evaluation.reviewed_count > 0 else "medium",
        description=(
            f"{evaluation.reviewed_count}/{evaluation.proposal_count} adapter proposal"
            f"{'' if evaluation.proposal_count == 1 else 's'} have reviewed truth."
        ),
        suggested_action=(
            "Use evidence agreement as a readiness signal, not final truth."
            if evaluation.reviewed_count > 0
            else "Create, convert, and correct adapter proposals to build readiness signal."
        ),
        link_path="model-adapters:evaluation",
    )
    add(
        item_id="proposal-review-path",
        label="Detection proposals have review path",
        status="ready" if adapter_contract_ready else "blocked",
        severity="low" if adapter_contract_ready else "high",
        description="Future detectors must normalize into DetectionProposal before visits/events are corrected.",
        suggested_action="Convert proposal evidence into reviewable visits/events, then correct labels.",
        link_path="detection-proposals",
    )
    return checklist


def _taxonomy_label_from_model(label: TaxonomyLabelModel) -> TaxonomyLabel:
    return TaxonomyLabel(
        id=label.id,
        label=label.label,
        display_name=label.display_name,
        category=LabelCategory(label.category),
        scientific_name=label.scientific_name,
        aliases=list(json.loads(label.aliases_json)),
        is_species=label.is_species,
        is_reviewable=label.is_reviewable,
        sort_order=label.sort_order,
    )


def _stream_from_model(stream: StreamModel) -> Stream:
    return Stream(
        id=stream.id,
        source_id=stream.source_id,
        name=stream.name,
        description=stream.description,
        is_live=stream.is_live,
    )


def _zone_from_model(zone: ZoneModel) -> Zone:
    return Zone(
        id=zone.id,
        stream_id=zone.stream_id,
        name=zone.name,
        zone_type=ZoneType(zone.zone_type),
        polygon=[Point(**point) for point in json.loads(zone.polygon_json)],
        is_active=zone.is_active,
    )


def _detection_from_model(detection: DetectionModel) -> Detection:
    bbox = BoundingBox(**json.loads(detection.bbox_json)) if detection.bbox_json else None
    return Detection(
        id=detection.id,
        label=detection.label,
        confidence=detection.confidence,
        zone_id=detection.zone_id,
        bbox=bbox,
    )


def _visit_from_model(visit: VisitModel) -> Visit:
    return Visit(
        id=visit.id,
        event_id=visit.event_id,
        subject_label=visit.subject_label,
        species_guess=visit.species_guess,
        confidence=visit.confidence,
        reviewed_label=visit.reviewed_label,
        review_status=ReviewStatus(visit.review_status),
        representative_media_path=visit.representative_media_path,
    )


def _media_asset_from_model(asset: MediaAssetModel) -> MediaAsset:
    return MediaAsset(
        id=asset.id,
        source_id=asset.source_id,
        stream_id=asset.stream_id,
        filename=asset.filename,
        content_type=asset.content_type,
        media_type=asset.media_type,
        local_path=asset.local_path,
        original_filename=asset.original_filename,
        file_size_bytes=asset.file_size_bytes,
        created_at=_as_utc(asset.created_at),
        notes=asset.notes,
    )


def _motion_evidence_from_model(evidence: MotionEvidenceModel) -> MotionEvidenceResponse:
    return MotionEvidenceResponse(
        id=evidence.id,
        source_id=evidence.source_id,
        stream_id=evidence.stream_id,
        zone_id=evidence.zone_id,
        start_frame_index=evidence.start_frame_index,
        end_frame_index=evidence.end_frame_index,
        best_frame_index=evidence.best_frame_index,
        start_time=evidence.start_time,
        end_time=evidence.end_time,
        best_frame_time=evidence.best_frame_time,
        peak_changed_ratio=evidence.peak_changed_ratio,
        triggered_frame_count=evidence.triggered_frame_count,
        scoring_config=dict(json.loads(evidence.scoring_config_json)),
        snapshot_media_asset_id=evidence.snapshot_media_asset_id,
        status=MotionEvidenceStatus(evidence.status),
        promoted_event_id=evidence.promoted_event_id,
        promoted_visit_id=evidence.promoted_visit_id,
        created_at=_as_utc(evidence.created_at),
        notes=evidence.notes,
    )


def _species_suggestion_from_model(
    suggestion: SpeciesSuggestionModel,
) -> SpeciesSuggestionResponse:
    return SpeciesSuggestionResponse(
        id=suggestion.id,
        source_id=suggestion.source_id,
        stream_id=suggestion.stream_id,
        event_id=suggestion.event_id,
        visit_id=suggestion.visit_id,
        media_asset_id=suggestion.media_asset_id,
        motion_evidence_id=suggestion.motion_evidence_id,
        adapter_id=suggestion.adapter_id,
        adapter_name=suggestion.adapter_name,
        suggested_label=suggestion.suggested_label,
        suggested_common_name=suggestion.suggested_common_name,
        suggested_scientific_name=suggestion.suggested_scientific_name,
        confidence=suggestion.confidence,
        rank=suggestion.rank,
        alternatives=list(json.loads(suggestion.alternatives_json)),
        evidence_region=(
            dict(json.loads(suggestion.evidence_region_json))
            if suggestion.evidence_region_json
            else None
        ),
        status=SpeciesSuggestionStatus(suggestion.status),
        created_at=_as_utc(suggestion.created_at),
        notes=suggestion.notes,
    )


def _detection_run_from_model(run: DetectionRunModel) -> DetectionRun:
    return DetectionRun(
        id=run.id,
        media_asset_id=run.media_asset_id,
        source=DetectionSource(run.source),
        summary=run.summary,
        status=DetectionRunStatus(run.status),
        created_at=_as_utc(run.created_at),
        completed_at=_as_utc(run.completed_at) if run.completed_at else None,
    )


def _detection_proposal_from_model(proposal: DetectionProposalModel) -> DetectionProposal:
    bbox = BoundingBox(**json.loads(proposal.bbox_json)) if proposal.bbox_json else None
    return DetectionProposal(
        id=proposal.id,
        run_id=proposal.run_id,
        media_asset_id=proposal.media_asset_id,
        stream_id=proposal.stream_id,
        zone_id=proposal.zone_id,
        event_id=proposal.event_id,
        visit_id=proposal.visit_id,
        label=proposal.label,
        confidence=proposal.confidence,
        bbox=bbox,
        suggested_event_type=proposal.suggested_event_type,
        suggested_subject_label=proposal.suggested_subject_label,
        suggested_species=proposal.suggested_species,
        status=DetectionProposalStatus(proposal.status),
        notes=proposal.notes,
        created_at=_as_utc(proposal.created_at),
        decided_at=_as_utc(proposal.decided_at) if proposal.decided_at else None,
    )


def _review_label_from_model(label: ReviewLabelModel) -> ReviewLabel:
    return ReviewLabel(
        id=label.id,
        target_type=label.target_type,
        target_id=label.target_id,
        label=label.label,
        notes=label.notes,
        created_at=_as_utc(label.created_at),
    )


def _dataset_export_from_model(dataset_export: DatasetExportModel) -> DatasetExport:
    return DatasetExport(
        id=dataset_export.id,
        name=dataset_export.name,
        status=ExportStatus(dataset_export.status),
        reviewed_only=dataset_export.reviewed_only,
        include_detections=dataset_export.include_detections,
        include_zone_context=dataset_export.include_zone_context,
        record_count=dataset_export.record_count,
        created_at=_as_utc(dataset_export.created_at),
    )


def _points_to_json(points: list[Point]) -> str:
    return json.dumps([point.model_dump() for point in points])


def _bbox_to_json(bbox: BoundingBox | None) -> str | None:
    if bbox is None:
        return None
    return json.dumps(bbox.model_dump())


def _detector_bbox_to_json(bbox) -> str | None:
    if bbox is None:
        return None
    return json.dumps(
        {
            "x": bbox.x,
            "y": bbox.y,
            "width": bbox.width,
            "height": bbox.height,
        }
    )


def _taxonomy_key(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def _freeform_label(value: str) -> str:
    return _taxonomy_key(value) or "unknown_animal"


def _display_name_from_label(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("-", "_").split("_") if part)


def _database_path_from_url(db_url: str) -> str | None:
    if not db_url.startswith("sqlite:///"):
        return None

    path = db_url.removeprefix("sqlite:///")
    if path in {"", ":memory:"}:
        return None
    return path


def _safe_filename(original_filename: str) -> str:
    filename = Path(original_filename or "imported-media").name or "imported-media"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip(".-")
    return safe or "imported-media"


def _folder_path(folder_path: str) -> Path:
    return Path(folder_path.strip()).expanduser() if folder_path.strip() else Path("")


def _media_type_for_path(path: Path) -> tuple[str, str] | None:
    return SUPPORTED_MEDIA_EXTENSIONS.get(path.suffix.lower())


def _is_external_url_preview_media_asset(asset: MediaAssetModel) -> bool:
    notes = asset.notes or ""
    return (
        "provider_key=external_url" in notes
        and "Saved explicit external_url still-image preview." in notes
    )


def _is_folder_import_media_asset(asset: MediaAssetModel) -> bool:
    notes = asset.notes or ""
    return (
        "provider_key=folder_import_future" in notes
        and "Imported explicit folder/trail-cam media as MediaAsset only." in notes
    )


def _media_asset_motion_evidence_provenance_kind(asset: MediaAssetModel) -> str:
    if _is_external_url_preview_media_asset(asset):
        return "external_url_preview"
    if _is_folder_import_media_asset(asset):
        return "folder_import"
    return "media_asset"


def _external_url_preview_note_fields(notes: str | None) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in (notes or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            fields[key] = value.strip()
    return fields


def _folder_import_media_notes(
    *,
    source_id: str,
    stream_id: str,
    zone_id: str | None,
    relative_source_path: str,
    original_filename: str,
    size_bytes: int | None,
    modified_at: datetime | None,
    imported_at: datetime,
    copy_mode: str,
    note: str | None,
) -> str:
    lines = [
        "Imported explicit folder/trail-cam media as MediaAsset only.",
        "Creates no MotionEvidence, Events, Visits, ReviewLabels, or truth.",
        "provider_key=folder_import_future",
        f"source_id={source_id}",
        f"stream_id={stream_id}",
        f"relative_source_path={relative_source_path}",
        f"original_filename={original_filename}",
        f"imported_at={imported_at.isoformat()}",
        f"copy_mode={copy_mode}",
    ]
    if zone_id is not None:
        lines.append(f"zone_id={zone_id}")
    if size_bytes is not None:
        lines.append(f"size_bytes={size_bytes}")
    if modified_at is not None:
        lines.append(f"modified_at={modified_at.isoformat()}")
    cleaned_note = _clean_optional_text(note)
    if cleaned_note is not None:
        lines.append(f"note={cleaned_note}")
    return "\n".join(lines)


def _folder_import_note_fields(notes: str | None) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in (notes or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            fields[key] = value.strip()
    return fields


def _parsed_note_datetime(value: str | None, warnings: list[str]) -> datetime | None:
    if value is None:
        return None
    try:
        return _as_utc(datetime.fromisoformat(value))
    except ValueError:
        warnings.append("Saved preview fetched_at metadata could not be parsed.")
        return None


def _saved_preview_provenance(note_fields: dict[str, str]) -> str:
    parts = ["external_url preview"]
    provider_key = _safe_provenance_value(note_fields.get("provider_key"))
    if provider_key is not None:
        parts.append(f"provider_key={provider_key}")
    url_host = _safe_provenance_value(note_fields.get("url_host"))
    if url_host is not None:
        parts.append(f"url_host={url_host}")
    return "; ".join(parts)


def _safe_provenance_value(value: str | None) -> str | None:
    cleaned = _clean_optional_text(value)
    if cleaned is None:
        return None
    return cleaned.replace("\n", " ").replace("\r", " ")[:160]


def _merge_notes(existing_notes: str | None, new_notes: str) -> str:
    if not existing_notes:
        return new_notes
    return f"{existing_notes}\n{new_notes}"


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
