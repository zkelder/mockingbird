"""SQLAlchemy models for product-level MockingBird persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


DEFAULT_STREAM_MONITORING_MODE = "off"
DEFAULT_STREAM_RUNTIME_STATE = "stopped"
DEFAULT_STREAM_MONITORING_INTERVAL_SECONDS = 1.5
DEFAULT_STREAM_MONITORING_QUIET_SECONDS = 30
DEFAULT_STREAM_MONITORING_MINIMUM_DETECTIONS = 1


class CameraSourceModel(Base):
    __tablename__ = "camera_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class StreamModel(Base):
    __tablename__ = "streams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("camera_sources.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SpeciesCandidatePackModel(Base):
    """Immutable candidate-bank version referenced by suggestion evidence."""

    __tablename__ = "species_candidate_packs"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_species_candidate_pack_status"),
        CheckConstraint("version >= 1", name="ck_species_candidate_pack_version"),
        CheckConstraint("candidate_count BETWEEN 2 AND 200", name="ck_species_candidate_pack_candidate_count"),
        CheckConstraint("length(content_sha256) = 64", name="ck_species_candidate_pack_content_sha256"),
        UniqueConstraint("display_name", "version", name="uq_species_candidate_pack_name_version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_sha256: Mapped[str] = mapped_column(String, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SpeciesCandidatePackMemberModel(Base):
    """Ordered taxonomy members; completed suggestion evidence never rewrites them."""

    __tablename__ = "species_candidate_pack_members"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_species_candidate_pack_member_position"),
        UniqueConstraint("pack_id", "taxonomy_label_id", name="uq_species_candidate_pack_member_taxonomy"),
    )

    pack_id: Mapped[str] = mapped_column(ForeignKey("species_candidate_packs.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    taxonomy_label_id: Mapped[str] = mapped_column(ForeignKey("taxonomy_labels.id"), nullable=False)


class StreamSpeciesCandidatePackSelectionModel(Base):
    """Per-Stream candidate-pack intent; missing rows resolve to the built-in pack."""

    __tablename__ = "stream_species_candidate_pack_selections"

    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), primary_key=True)
    # Deliberately no FK: a partially restored or archived identifier must fall back
    # safely instead of preventing the Stream from opening.
    candidate_pack_id: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StreamMonitoringPolicyModel(Base):
    """Durable user intent for Stream monitoring; it never proves runtime activity."""

    __tablename__ = "stream_monitoring_policies"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('off', 'armed', 'paused')",
            name="ck_stream_monitoring_policy_mode",
        ),
    )

    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), primary_key=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    auto_create_review_candidates: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluation_interval_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    quiet_period_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_detection_count: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    armed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class StreamRuntimeCheckpointModel(Base):
    """Last-known operational metadata; it is never evidence or reviewed truth."""

    __tablename__ = "stream_runtime_checkpoints"
    __table_args__ = (
        CheckConstraint(
            "actual_state IN ('stopped', 'starting', 'running', 'backoff', "
            "'blocked', 'stopping', 'interrupted')",
            name="ck_stream_runtime_checkpoint_state",
        ),
    )

    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), primary_key=True)
    observed_policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_state: Mapped[str] = mapped_column(String, nullable=False)
    app_instance_id: Mapped[str | None] = mapped_column(String, nullable=True)
    runtime_generation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    last_start_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_healthy_frame_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_evidence_persisted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_evidence_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_failure_code: Mapped[str | None] = mapped_column(String, nullable=True)
    last_clean_stop_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String, nullable=True)
    consecutive_failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_stop_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    start_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_handoff_count: Mapped[int] = mapped_column(Integer, nullable=False)
    safety_hold_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class MonitoringExposureIntervalModel(Base):
    """A bounded healthy-frame interval; it is operational history, never evidence."""

    __tablename__ = "monitoring_exposure_intervals"
    __table_args__ = (
        CheckConstraint(
            "ended_at IS NULL OR ended_at > started_at",
            name="ck_monitoring_exposure_interval_positive_duration",
        ),
        CheckConstraint(
            "last_confirmed_fresh_at >= started_at",
            name="ck_monitoring_exposure_interval_fresh_after_start",
        ),
        CheckConstraint(
            "close_reason IS NULL OR close_reason IN "
            "('monitoring_disabled', 'session_stopped', 'provider_failure', "
            "'fresh_frame_stale', 'application_shutdown', 'unclean_restart', "
            "'source_unusable', 'runtime_generation_replaced')",
            name="ck_monitoring_exposure_interval_close_reason",
        ),
        Index(
            "uq_monitoring_exposure_intervals_one_open_stream",
            "stream_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
        ),
        Index(
            "ix_monitoring_exposure_intervals_stream_started",
            "stream_id",
            "started_at",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("camera_sources.id"), nullable=True
    )
    runtime_generation_id: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_confirmed_fresh_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CameraHealthIncidentModel(Base):
    """Bounded operational history; never a frame log, evidence record, or truth."""

    __tablename__ = "camera_health_incidents"
    __table_args__ = (
        Index("ix_camera_health_incidents_stream_updated", "stream_id", "updated_at"),
        Index("ix_camera_health_incidents_stream_open", "stream_id", "resolved_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    condition_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    alert_id: Mapped[str | None] = mapped_column(String, nullable=True)


class CameraConfigurationRevisionModel(Base):
    """Bounded redacted history for intentional in-place camera configuration changes."""

    __tablename__ = "camera_configuration_revisions"
    __table_args__ = (
        UniqueConstraint(
            "stream_id",
            "idempotency_key",
            name="uq_camera_configuration_revision_stream_idempotency",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("camera_sources.id"), nullable=False)
    provider_key: Mapped[str] = mapped_column(String, nullable=False)
    changed_fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    change_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    preview_token: Mapped[str] = mapped_column(String, nullable=False)
    restart_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    restart_requested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    desired_mode: Mapped[str] = mapped_column(String, nullable=False)
    actual_state_before: Mapped[str] = mapped_column(String, nullable=False)
    actual_state_after: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StreamMonitoringOperationModel(Base):
    """Durable idempotency record for explicit monitoring controls only."""

    __tablename__ = "stream_monitoring_operations"
    __table_args__ = (
        CheckConstraint(
            "operation IN ('enable', 'disable', 'retry')",
            name="ck_stream_monitoring_operation_kind",
        ),
        Index("ix_stream_monitoring_operations_stream_id", "stream_id"),
    )

    idempotency_key: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CameraSetupOperationModel(Base):
    """Idempotency record for one completed guided camera setup."""

    __tablename__ = "camera_setup_operations"

    idempotency_key: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("camera_sources.id"), nullable=False)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ZoneModel(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    zone_type: Mapped[str] = mapped_column(String, nullable=False)
    polygon_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    monitoring_policy_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    primary_zone_id: Mapped[str | None] = mapped_column(
        ForeignKey("zones.id"), nullable=True
    )
    review_status: Mapped[str] = mapped_column(String, nullable=False)


class DetectionModel(Base):
    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class VisitModel(Base):
    __tablename__ = "visits"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False)
    subject_label: Mapped[str] = mapped_column(String, nullable=False)
    species_guess: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewed_label: Mapped[str | None] = mapped_column(String, nullable=True)
    review_status: Mapped[str] = mapped_column(String, nullable=False)
    representative_media_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # A Visit can be reassigned without rewriting the Event's original context.
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    is_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VisitOrganizationModel(Base):
    """User-owned organization state; it is deliberately separate from ReviewLabel truth."""

    __tablename__ = "visit_organization"
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), primary_key=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    inherited_from_visit_id: Mapped[str | None] = mapped_column(
        ForeignKey("visits.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)


class VisitCollectionModel(Base):
    """A local user-curated Visit gallery; it never changes reviewed truth or media."""

    __tablename__ = "visit_collections"
    __table_args__ = (
        Index("ix_visit_collections_active_name", "archived_at", "normalized_name"),
        Index(
            "uq_visit_collections_active_normalized_name",
            "normalized_name",
            unique=True,
            sqlite_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)


class VisitCollectionMembershipModel(Base):
    """A normalized user-owned relationship; memberships never duplicate media."""

    __tablename__ = "visit_collection_memberships"
    __table_args__ = (Index("ix_visit_collection_memberships_visit_id", "visit_id"),)

    collection_id: Mapped[str] = mapped_column(
        ForeignKey("visit_collections.id"), primary_key=True
    )
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VisitTagModel(Base):
    """A lightweight local label for organizing Visits; never reviewed truth."""

    __tablename__ = "visit_tags"
    __table_args__ = (
        Index(
            "uq_visit_tags_active_normalized_name",
            "normalized_name",
            unique=True,
            sqlite_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)


class VisitTagMembershipModel(Base):
    __tablename__ = "visit_tag_memberships"
    __table_args__ = (Index("ix_visit_tag_memberships_visit_id", "visit_id"),)

    tag_id: Mapped[str] = mapped_column(ForeignKey("visit_tags.id"), primary_key=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class YardMapModel(Base):
    """One optional local spatial context; it never calibrates a camera or writes truth."""

    __tablename__ = "yard_maps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    background_relative_path: Mapped[str | None] = mapped_column(String, nullable=True)
    background_content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    background_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    background_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canvas_width: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas_height: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)


class YardMapStreamPlacementModel(Base):
    __tablename__ = "yard_map_stream_placements"
    __table_args__ = (Index("ix_yard_map_stream_placements_stream_id", "stream_id"),)

    map_id: Mapped[str] = mapped_column(ForeignKey("yard_maps.id"), primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), primary_key=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    heading_degrees: Mapped[float] = mapped_column(Float, nullable=False)
    field_of_view_degrees: Mapped[float] = mapped_column(Float, nullable=False)
    display_scale: Mapped[float | None] = mapped_column(Float, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)


class YardMapZonePlacementModel(Base):
    __tablename__ = "yard_map_zone_placements"
    __table_args__ = (Index("ix_yard_map_zone_placements_zone_id", "zone_id"),)

    map_id: Mapped[str] = mapped_column(ForeignKey("yard_maps.id"), primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"), primary_key=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    area_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)


class VisitEvidenceLinkModel(Base):
    """A bounded Visit-to-media association; deleting a link never deletes media."""

    __tablename__ = "visit_evidence_links"
    __table_args__ = (
        UniqueConstraint("visit_id", "media_asset_id", name="uq_visit_evidence_media"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), nullable=False)
    media_asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_role: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="monitoring_frame",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VisitRelationshipModel(Base):
    """Durable split/merge provenance between a superseded Visit and its result."""

    __tablename__ = "visit_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_visit_id",
            "result_visit_id",
            "relationship_type",
            name="uq_visit_relationship",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), nullable=False)
    result_visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VisitCurationHistoryModel(Base):
    """Append-only, user-facing audit facts for structural Visit curation."""

    __tablename__ = "visit_curation_history"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_visit_curation_key"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    prior_zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    result_visit_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MediaAssetModel(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("camera_sources.id"), nullable=True
    )
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str] = mapped_column(String, nullable=False)
    local_path: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # v24 provenance is evidence-only: no field here can imply reviewed truth.
    parent_media_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_assets.id"),
        nullable=True,
    )
    evidence_role: Mapped[str | None] = mapped_column(String, nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capture_profile_id: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_track_box_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_padded_crop_box_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    geometry_transform_id: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger_id: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capture_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alignment_status: Mapped[str | None] = mapped_column(String, nullable=True)
    alignment_failure_code: Mapped[str | None] = mapped_column(String, nullable=True)
    # v26 reviewer refinement keeps an immutable source-relative crop lineage.
    normalized_crop_box_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    derived_from_visit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    derived_from_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    derived_from_zone_id: Mapped[str | None] = mapped_column(String, nullable=True)
    parent_image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    derivation_source: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_effective_crop_media_asset_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )


class StorageRetentionSettingsModel(Base):
    """One durable, deliberately conservative local media-retention policy."""

    __tablename__ = "storage_retention_settings"

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    automatic_cleanup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cleanup_frequency: Mapped[str] = mapped_column(String, nullable=False)
    retain_unresolved_visit_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    retain_reviewed_bird_wildlife_evidence: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    reviewed_non_bird_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    superseded_evidence_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    orphaned_media_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_managed_media_bytes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_automatic_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_automatic_result: Mapped[str | None] = mapped_column(String, nullable=True)
    # Settings writes have their own request identity; automatic-run status remains
    # an operational observation and must never double as an idempotency ledger.
    last_settings_idempotency_key: Mapped[str | None] = mapped_column(
        String, nullable=True
    )


class StorageCleanupBatchModel(Base):
    """Durable preview, quarantine, restore, and purge audit state for managed media."""

    __tablename__ = "storage_cleanup_batches"
    __table_args__ = (
        UniqueConstraint("preview_token", name="uq_storage_cleanup_preview_token"),
        UniqueConstraint("idempotency_key", name="uq_storage_cleanup_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    preview_token: Mapped[str] = mapped_column(String, nullable=False)
    state_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    last_restore_idempotency_key: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    last_purge_idempotency_key: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recovery_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    safe_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class StorageCleanupItemModel(Base):
    """One staged managed-media move, with enough metadata for compatible restoration."""

    __tablename__ = "storage_cleanup_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "media_asset_id", name="uq_storage_cleanup_item"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("storage_cleanup_batches.id"), nullable=False
    )
    media_asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    original_local_path: Mapped[str] = mapped_column(Text, nullable=False)
    quarantine_relative_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_links_json: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductAlertModel(Base):
    """Durable local attention item with a product action, never a runtime command."""

    __tablename__ = "product_alerts"
    __table_args__ = (
        UniqueConstraint("deduplication_key", "condition_version", name="uq_product_alert_condition"),
        Index("ix_product_alerts_created_at", "created_at"),
        Index("ix_product_alerts_category_created", "category", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stream_id: Mapped[str | None] = mapped_column(String, nullable=True)
    zone_id: Mapped[str | None] = mapped_column(String, nullable=True)
    visit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cleanup_context: Mapped[str | None] = mapped_column(String, nullable=True)
    deduplication_key: Mapped[str] = mapped_column(String, nullable=False)
    condition_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    condition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    action_parameters_json: Mapped[str] = mapped_column(Text, nullable=False)


class DetectionRunModel(Base):
    __tablename__ = "detection_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    media_asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DetectionProposalModel(Base):
    __tablename__ = "detection_proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("detection_runs.id"), nullable=False)
    media_asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id"), nullable=False
    )
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    visit_id: Mapped[str | None] = mapped_column(ForeignKey("visits.id"), nullable=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_event_type: Mapped[str] = mapped_column(String, nullable=False)
    suggested_subject_label: Mapped[str] = mapped_column(String, nullable=False)
    suggested_species: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BioClipIdentificationAttemptModel(Base):
    """Durable evidence for one explicit manual BioCLIP attempt, never review truth."""

    __tablename__ = "bioclip_identification_attempts"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('visit', 'event')",
            name="ck_bioclip_attempt_target_type",
        ),
        CheckConstraint(
            "(target_type = 'visit' AND visit_id IS NOT NULL AND visit_id = target_id) "
            "OR (target_type = 'event' AND event_id IS NOT NULL "
            "AND event_id = target_id AND visit_id IS NULL)",
            name="ck_bioclip_attempt_exact_target",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN "
            "('succeeded', 'no_result', 'timed_out', 'failed', 'unsupported', 'cancelled')",
            name="ck_bioclip_attempt_outcome",
        ),
        CheckConstraint(
            "(outcome IS NULL AND completed_at IS NULL "
            "AND resulting_species_suggestion_id IS NULL "
            "AND error_code IS NULL AND error_stage IS NULL AND error_detail IS NULL) "
            "OR (outcome IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_bioclip_attempt_lifecycle",
        ),
        CheckConstraint(
            "(outcome = 'succeeded' AND resulting_species_suggestion_id IS NOT NULL "
            "AND error_code IS NULL AND error_stage IS NULL AND error_detail IS NULL) "
            "OR ((outcome IS NULL OR outcome <> 'succeeded') "
            "AND resulting_species_suggestion_id IS NULL)",
            name="ck_bioclip_attempt_result_link",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome = 'succeeded' OR error_code IS NOT NULL",
            name="ck_bioclip_attempt_non_success_error_code",
        ),
        CheckConstraint(
            "error_stage IS NULL OR error_stage IN "
            "('configuration', 'input_preparation', 'crop_preparation', "
            "'process_startup', 'model_load', 'inference', 'output_parsing', "
            "'eligibility_revalidation', 'persistence')",
            name="ck_bioclip_attempt_error_stage",
        ),
        CheckConstraint(
            "error_code IS NULL OR length(error_code) <= 80",
            name="ck_bioclip_attempt_error_code_length",
        ),
        CheckConstraint(
            "error_detail IS NULL OR length(error_detail) <= 256",
            name="ck_bioclip_attempt_error_detail_length",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_bioclip_attempt_completion_time",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_bioclip_attempt_duration",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('unsupported', 'cancelled') "
            "OR duration_ms IS NOT NULL",
            name="ck_bioclip_attempt_measured_duration",
        ),
        CheckConstraint(
            "timeout_limit_ms > 0",
            name="ck_bioclip_attempt_timeout_limit",
        ),
        CheckConstraint(
            "(outcome = 'timed_out' AND timeout_exceeded = 1) "
            "OR ((outcome IS NULL OR outcome <> 'timed_out') AND timeout_exceeded = 0)",
            name="ck_bioclip_attempt_timeout_outcome",
        ),
        CheckConstraint(
            "crop_source IS NULL OR crop_source IN ('megadetector', 'activity', 'full_frame')",
            name="ck_bioclip_attempt_crop_source",
        ),
        CheckConstraint(
            "candidate_set_count IS NULL OR candidate_set_count >= 0",
            name="ck_bioclip_attempt_candidate_count",
        ),
        CheckConstraint(
            "candidate_set_sha256 IS NULL OR length(candidate_set_sha256) = 64",
            name="ck_bioclip_attempt_candidate_sha256",
        ),
        CheckConstraint(
            "candidate_manifest_complete = 0 OR "
            "(candidate_manifest_json IS NOT NULL AND candidate_set_count > 0 "
            "AND candidate_set_sha256 IS NOT NULL)",
            name="ck_bioclip_attempt_complete_manifest",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome <> 'succeeded' OR "
            "(crop_source IS NOT NULL AND crop_provenance_json IS NOT NULL "
            "AND model_provenance_json IS NOT NULL AND preprocessing_json IS NOT NULL "
            "AND candidate_manifest_complete = 1)",
            name="ck_bioclip_attempt_success_provenance",
        ),
        CheckConstraint(
            "provenance_schema_version >= 1",
            name="ck_bioclip_attempt_provenance_version",
        ),
        UniqueConstraint(
            "resulting_species_suggestion_id",
            name="uq_bioclip_attempt_resulting_suggestion",
        ),
        Index(
            "ix_bioclip_attempt_target_started",
            "target_type",
            "target_id",
            "started_at",
        ),
        Index(
            "ix_bioclip_attempt_outcome_started",
            "outcome",
            "started_at",
        ),
        Index(
            "ix_bioclip_attempt_media_started",
            "media_asset_id",
            "started_at",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    visit_id: Mapped[str | None] = mapped_column(ForeignKey("visits.id"), nullable=True)
    media_asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id"), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("camera_sources.id"),
        nullable=True,
    )
    stream_id: Mapped[str | None] = mapped_column(
        ForeignKey("streams.id"), nullable=True
    )
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    # MotionEvidence currently lives in ProductRepository, so this identifier stays
    # an indexed link rather than making storage metadata depend on import order.
    motion_evidence_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    detection_proposal_id: Mapped[str | None] = mapped_column(
        ForeignKey("detection_proposals.id"),
        nullable=True,
    )
    # SpeciesSuggestion has the same repository-owned metadata boundary.
    resulting_species_suggestion_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    adapter_id: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_exceeded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    crop_source: Mapped[str | None] = mapped_column(String, nullable=True)
    crop_provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    preprocessing_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_manifest_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_set_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_set_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_set_version: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_pack_id: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_pack_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_pack_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_manifest_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )


class ReviewIdentificationAssistantRunModel(Base):
    """One explicit reviewer request that may inspect a bounded saved Visit sequence."""

    __tablename__ = "review_identification_assistant_runs"
    __table_args__ = (
        CheckConstraint(
            "evidence_mode IN ('primary_only', 'all_retained_evidence')",
            name="ck_review_identification_assistant_evidence_mode",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'no_result', 'unavailable', 'failed')",
            name="ck_review_identification_assistant_status",
        ),
        CheckConstraint(
            "request_origin = 'user_triggered_review_assistance'",
            name="ck_review_identification_assistant_origin",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_review_identification_assistant_idempotency",
        ),
        Index(
            "ix_review_identification_assistant_visit_started",
            "visit_id",
            "started_at",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    evidence_mode: Mapped[str] = mapped_column(String, nullable=False)
    selected_media_asset_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_configuration_sha256: Mapped[str] = mapped_column(String, nullable=False)
    request_origin: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)


class TaxonomyLabelModel(Base):
    __tablename__ = "taxonomy_labels"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    scientific_name: Mapped[str | None] = mapped_column(String, nullable=True)
    aliases_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_species: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_reviewable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ReviewLabelModel(Base):
    __tablename__ = "review_labels"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reversal_of_review_label_id: Mapped[str | None] = mapped_column(String, nullable=True)
    prior_review_status: Mapped[str | None] = mapped_column(String, nullable=True)
    prior_reviewed_label: Mapped[str | None] = mapped_column(String, nullable=True)
    prior_event_review_status: Mapped[str | None] = mapped_column(String, nullable=True)
    fast_review_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    fast_review_idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    supersedes_review_label_id: Mapped[str | None] = mapped_column(String, nullable=True)
    review_action: Mapped[str | None] = mapped_column(String, nullable=True)
    revision_idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    # Review Decision Provenance / Truth Boundary v1 (see
    # docs/review-decision-provenance-contract.md and
    # mockingbird.review_provenance): `NULL` means "no explicit origin was
    # recorded" -- either a legacy row that predates this column, or a
    # create request that omitted the field. It never means "human" by
    # default; `mockingbird.review_provenance.is_authority_eligible` is the
    # only place that decides whether a given origin may establish or
    # correct durable reviewed truth.
    review_origin: Mapped[str | None] = mapped_column(String, nullable=True)
    # Free-text "who/what" -- required by application-layer validation for
    # `imported_curated`/`agent_diagnostic` origins, optional otherwise
    # (there is no reviewer identity/account system).
    reviewer_identity: Mapped[str | None] = mapped_column(String, nullable=True)


class DatasetExportModel(Base):
    __tablename__ = "dataset_exports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    reviewed_only: Mapped[bool] = mapped_column(Boolean, nullable=False)
    include_detections: Mapped[bool] = mapped_column(Boolean, nullable=False)
    include_zone_context: Mapped[bool] = mapped_column(Boolean, nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    selected_visit_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class ActivityLibrarySavedViewModel(Base):
    """Local organizational metadata; it never duplicates Visit evidence or truth."""

    __tablename__ = "activity_library_saved_views"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AppSetupStateModel(Base):
    """One durable first-run/onboarding progress record (see
    docs/local-product-packaging-design.md). Seeded once by
    `initialize_database`/its schema-29 migration -- never recomputed from
    current Source/Stream counts -- so an installation's onboarding state
    cannot flip merely because a user later removes every camera."""

    __tablename__ = "app_setup_state"

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    current_step: Mapped[str] = mapped_column(String, nullable=False)
    last_created_stream_id: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CameraNodePendingSetupModel(Base):
    """A durable, server-only record of a Camera Node pairing not yet
    promoted into a Source (see docs/camera-node-pairing-persistence-design.md).

    Exists so that once a Node accepts its one-time pairing code, the
    resulting credential is never held only in React state, sessionStorage,
    or process memory for the rest of guided setup -- a browser refresh, a
    closed tab, or an application restart can always recover it. The
    credential is kept exactly the way a completed Source already keeps one
    (plain local SQLite -- this product's existing trust boundary -- never
    returned by any API response and never logged); this row is deleted the
    moment setup actually completes and the credential is copied into
    `SourceProviderConfigurationModel`. `status` distinguishes a pairing
    still believed usable (`active`) from one the Node has since rejected
    (`needs_renewal`), so a resumed wizard can tell "continue setup" from
    "pairing needs to be renewed" without re-probing the Node on every load.
    """

    __tablename__ = "camera_node_pending_setups"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'needs_renewal')",
            name="ck_camera_node_pending_setup_status",
        ),
    )

    token: Mapped[str] = mapped_column(String, primary_key=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    api_version: Mapped[str] = mapped_column(String, nullable=False)
    base_address: Mapped[str] = mapped_column(String, nullable=False)
    credential: Mapped[str] = mapped_column(String, nullable=False)
    capability_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    recommended_snapshot_timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    cameras_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    selected_camera_id: Mapped[str | None] = mapped_column(String, nullable=True)
    camera_name: Mapped[str | None] = mapped_column(String, nullable=True)
    stream_name: Mapped[str | None] = mapped_column(String, nullable=True)
    zone_name: Mapped[str | None] = mapped_column(String, nullable=True)
    zone_type: Mapped[str | None] = mapped_column(String, nullable=True)
    polygon_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitivity: Mapped[str | None] = mapped_column(String, nullable=True)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
