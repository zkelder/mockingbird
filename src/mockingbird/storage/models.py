"""SQLAlchemy models for product-level MockingBird persistence."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
    # Boot Identity + Autonomous Recovery v1 (schema 37): a durable,
    # session-independent "last seen" fact for a paired Camera Node --
    # updated wherever the host already talks to the Node (today: the
    # existing, already-throttled Observation Engine exposure checkpoint;
    # see `ProductRepository.record_observation_exposure_frame`), never a
    # new poller. Nullable/no default: every Source predating this column,
    # and any non-Camera-Node Source, correctly reads back
    # `camera_node_last_seen_at=None` -- "not tracked," never a fabricated
    # timestamp. See "Host-side state" in docs/camera-node-installer
    # -design.md.
    camera_node_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    camera_node_boot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # When the *current* `camera_node_boot_id` was first observed -- only
    # advances when the boot id actually changes, so this doubles as
    # "how long (from the host's own observation) has this boot been
    # running."
    camera_node_boot_first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    camera_node_service_version: Mapped[str | None] = mapped_column(String, nullable=True)
    # Bounded (<=5 entries) JSON list of the most recent boot-id
    # transitions -- `[{"boot_id": ..., "first_seen_at": ...}, ...]`,
    # newest first -- deliberately not an unbounded historical ledger (see
    # milestone instruction #10). Restart/boot-loop instability is
    # interpreted from this bounded window, never stored as its own
    # separately-growing fact.
    camera_node_recent_boot_transitions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Reprovision / Replacement Recovery v1 (schema 38): bounded, "most
    # recent transition only" provenance -- never a growing hardware-asset
    # ledger (see milestone instruction #15). Set only by a *confirmed*
    # `camera_node_identity_changed` override (see
    # `_camera_configuration_proposed_config`); an ordinary same-identity
    # credential repair never touches these. Nullable/no default: a Source
    # whose Camera Node was never replaced correctly reads back
    # `camera_node_identity_replaced_at=None` -- "never replaced," not a
    # fabricated event. See docs/camera-node-reprovision-recovery-design.md.
    camera_node_prior_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    camera_node_identity_replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    camera_node_replacement_reason: Mapped[str | None] = mapped_column(String, nullable=True)


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


class StreamObservationIntentModel(Base):
    """Native-Windows Field Reliability Corrections v1 (schema 61): the
    durable answer to "should this Stream be observing?"

    Operational intent -- never evidence, never reviewed truth, and it
    carries no observation content of any kind. Written only at a real
    product action (Start observing / Stop observing / archiving a Source),
    and deliberately **not** written by any runtime teardown
    (`app_shutdown`, `repository_reconfigured`, `local_backup_restore`):
    that is exactly what lets `CameraNodeRecoverySupervisor` tell "the Host
    restarted while observation was supposed to be running" apart from "a
    person pressed Stop," which nothing in the product could distinguish
    across a process restart before this table existed. Because the record
    is durable rather than a clean-shutdown callback, an abrupt process or
    OS kill is covered by the identical mechanism -- it writes nothing, and
    the intent from the user's original Start is simply still here.

    `stream_id` is the primary key, so a duplicate intent for one Stream is
    not representable. An absent row means "no intent has ever been
    expressed" and is never read as `observing` -- the product must never
    blind-start every Camera Node on boot. Losing the row degrades to
    exactly the pre-milestone behaviour (no automatic resume), never to a
    wrong one.

    See docs/native-windows-field-reliability-corrections-v1-contract.md,
    "The durable observation-intent contract," including why
    `stream_monitoring_policies`/`stream_runtime_checkpoints`/
    `monitoring_exposure_intervals` were each checked and could not carry
    this.
    """

    __tablename__ = "stream_observation_intents"
    __table_args__ = (
        CheckConstraint(
            "desired_state IN ('observing', 'stopped')",
            name="ck_stream_observation_intent_desired_state",
        ),
    )

    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), primary_key=True)
    desired_state: Mapped[str] = mapped_column(String, nullable=False)
    # Why `desired_state` last *changed* -- `user_started`, `user_stopped`,
    # `source_archived`, `automatic_resume`. Diagnostic only: no recovery
    # decision reads it, so a future reason needs no code change here.
    requested_reason: Mapped[str] = mapped_column(String, nullable=False)
    # When `desired_state` last actually changed, as distinct from
    # `updated_at` (every write). A repeated Start observing on an
    # already-`observing` Stream must not look like a fresh intent.
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
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
    # Performance / Scale / Stability Closure v1 (schema 60). Measured at an
    # ordinary established-install size (2,813 Visits / 11,244 media assets):
    # this table carried no secondary index at all, so every lookup by this
    # foreign key was a full table scan. See
    # docs/performance-scale-stability-closure-v1-report.md for the measured
    # before/after and the query plan each index was chosen against.
    __table_args__ = (
        Index("ix_events_stream_started", "stream_id", "started_at"),
        Index("ix_events_review_status", "review_status"),
    )

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
    # Performance / Scale / Stability Closure v1 (schema 60). Measured at an
    # ordinary established-install size (2,813 Visits / 11,244 media assets):
    # this table carried no secondary index at all, so every lookup by this
    # foreign key was a full table scan. See
    # docs/performance-scale-stability-closure-v1-report.md for the measured
    # before/after and the query plan each index was chosen against.
    __table_args__ = (Index("ix_detections_event", "event_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class VisitModel(Base):
    __tablename__ = "visits"
    # Performance / Scale / Stability Closure v1 (schema 60). Measured at an
    # ordinary established-install size (2,813 Visits / 11,244 media assets):
    # this table carried no secondary index at all, so every lookup by this
    # foreign key was a full table scan. See
    # docs/performance-scale-stability-closure-v1-report.md for the measured
    # before/after and the query plan each index was chosen against.
    __table_args__ = (
        Index("ix_visits_event", "event_id"),
        Index("ix_visits_review_status", "review_status", "is_superseded"),
    )

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
    # Performance / Scale / Stability Closure v1 (schema 60). Measured at an
    # ordinary established-install size (2,813 Visits / 11,244 media assets):
    # this table carried no secondary index at all, so every lookup by this
    # foreign key was a full table scan. See
    # docs/performance-scale-stability-closure-v1-report.md for the measured
    # before/after and the query plan each index was chosen against.
    __table_args__ = (
        Index("ix_media_assets_local_path", "local_path"),
        Index("ix_media_assets_stream", "stream_id"),
    )

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
    # Localization Attribution / Detection Geometry Lineage v1 (schema 33,
    # see docs/localization-attribution-contract.md): one serialized
    # `contracts.GeometryAttribution` JSON object explaining where this
    # asset's own `normalized_track_box_json` actually came from (a genuine
    # detector hit, tracker-support patch match, or stale carried-forward
    # box) and whether this image provably represents the same moment as
    # that geometry's own source observation. Nullable with no default:
    # every row created before this column existed, and every asset whose
    # producer has no basis to compute it (for example the legacy
    # `alignment_status`/`alignment_failure_code` motion-evidence path
    # above, unrelated to the Observation Engine v2 candidate-Visit path
    # this column serves), reads back `None` -- never a fabricated
    # attribution (see "no fabricated confidence for legacy records" in
    # product-doctrine.md). Diagnostic lineage only; nothing reads this
    # column as species/animal-presence truth.
    geometry_attribution_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.8 Offline
    # recorded video"): the source clip's own known duration, honest
    # acquisition-effort provenance for a recorded-video/camera-trap-video
    # import -- never wired into `MonitoringExposureIntervalModel` or
    # Today's coverage/maturity math (see "II.10 Offline vs monitoring
    # coverage"): importing a clip must never imply continuous monitoring.
    # `None` for every image and for any video imported before this column
    # existed or whose duration ffprobe could not determine -- an honest
    # "not known," never a fabricated zero.
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Acoustic / BirdNET Observation Foundation v1 (schema 43, see docs/
    # acoustic-birdnet-observation-foundation-v1-contract.md): sample-rate/
    # channel metadata for an audio `media_type` asset. `None` for every
    # image/video row and for any audio asset whose source metadata could
    # not be determined -- an honest "not known," never a fabricated value,
    # mirroring `duration_seconds`'s identical discipline immediately above.
    audio_sample_rate_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_channel_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Acoustic Runtime & Quality v1 (schema 44): `True` only for a segment
    # `ProductRepository.create_audio_segment_media_asset` itself imported
    # from an automatic capture/simulation source; `False`/default for
    # every other row, including every existing pre-migration row and
    # every asset a human explicitly imported (`create_media_import`/
    # `import_folder_media`). The one and only eligibility gate for
    # `run_working_audio_retention_sweep` -- found via review: without an
    # explicit positive marker, that sweep could not honestly distinguish
    # its own ephemeral working audio from a user's deliberately uploaded
    # recording that simply has not (yet) been linked as evidence, and
    # would delete the latter after its TTL. See that method's own
    # docstring.
    acoustic_working_segment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


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
    # Appliance / Storage / Privacy / Recovery v1, Phase D (schema 49): the
    # one new, opt-in retention lever for the `linked_evidence_or_analysis`
    # category (a MediaAsset referenced only by a rejected/suppressed
    # detection/analysis record, never by a Visit) -- previously protected
    # forever with no lever at all. `None` (every existing installation,
    # and the default for a new one) preserves that exact protected-forever
    # behavior; a user must explicitly opt in to an age threshold before any
    # of this category ever becomes cleanup-eligible. See
    # `ProductRepository._storage_retention_evaluation`.
    rejected_analysis_media_age_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True
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


class UserNotificationPreferenceModel(Base):
    """Calm Attention & Notifications v1 (schema 56): one signed-in user's
    own attention-delivery preferences -- the first per-user settings row
    in the product (every other settings table, e.g.
    `EnvironmentalContextSettingsModel`, is a Host-wide singleton). The
    underlying `ProductAlertModel` condition stays observatory-level and
    shared; only what one person is shown/notified about is per-user. See
    docs/calm-attention-notifications-v1-report.md."""

    __tablename__ = "user_notification_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    discovery_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    insight_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    needs_help_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    observatory_health_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    browser_notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quiet_hours_start_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=22 * 60)
    quiet_hours_end_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=7 * 60)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DetectionRunModel(Base):
    __tablename__ = "detection_runs"
    # Performance / Scale / Stability Closure v1 (schema 60). Measured at an
    # ordinary established-install size (2,813 Visits / 11,244 media assets):
    # this table carried no secondary index at all, so every lookup by this
    # foreign key was a full table scan. See
    # docs/performance-scale-stability-closure-v1-report.md for the measured
    # before/after and the query plan each index was chosen against.
    __table_args__ = (Index("ix_detection_runs_media", "media_asset_id"),)

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
    # Performance / Scale / Stability Closure v1 (schema 60). Measured at an
    # ordinary established-install size (2,813 Visits / 11,244 media assets):
    # this table carried no secondary index at all, so every lookup by this
    # foreign key was a full table scan. See
    # docs/performance-scale-stability-closure-v1-report.md for the measured
    # before/after and the query plan each index was chosen against.
    __table_args__ = (
        Index("ix_detection_proposals_run", "run_id"),
        Index("ix_detection_proposals_visit", "visit_id"),
    )

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
    # Performance / Scale / Stability Closure v1 (schema 60). Measured at an
    # ordinary established-install size (2,813 Visits / 11,244 media assets):
    # this table carried no secondary index at all, so every lookup by this
    # foreign key was a full table scan. See
    # docs/performance-scale-stability-closure-v1-report.md for the measured
    # before/after and the query plan each index was chosen against.
    __table_args__ = (Index("ix_review_labels_target", "target_type", "target_id"),)

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
    # Local Identity, Multi-User & Organization Access v1 (schema 50): the
    # durable, resolvable actor reference `reviewer_identity` was explicitly
    # documented above as never having. `NULL` for every row created before
    # this column existed (or created by a non-interactive/offline pathway
    # that has no signed-in user -- imported/curated data, an offline
    # replay/diagnostic script) -- see docs/local-identity-multi-user-
    # contract.md "Review attribution": history is never rewritten to
    # invent an actor. Populated only by the authenticated-HTTP review
    # handlers in mockingbird.api.main, which also overwrite
    # `reviewer_identity`/`review_origin` with the signed-in user's own
    # display name / `"human"` for that same request -- never trusted from
    # client-supplied payload fields once a session exists.
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    # Site-Specific Learning & Local Adaptation v1 (schema 53, see
    # docs/scene-confusor-suspicion-contract.md, "Reviewed-negative-evidence
    # suspicion"): the `SceneConfusorRegionModel.id` this specific label
    # actually incremented (`reviewed_real_count` or `reviewed_false_count`),
    # stamped only when this row was authority-eligible AND its target
    # Visit's evidence geometry matched an existing region at write time.
    # `NULL` for every row that never touched a region (most reviews) and
    # for every row created before this column existed. A deliberate soft
    # reference, not a `ForeignKey` -- a region can be purged (TTL, LRU,
    # reconfiguration invalidation) independently of this audit trail, and a
    # stale id on an old, immutable history row is harmless. Recorded so a
    # later revision/reopen of *this exact* label can retract *exactly* the
    # contribution it made -- deriving the match again from the Visit's own
    # geometry at retraction time was considered and rejected: a region's
    # own `representative_box` drifts (incremental running mean) as more
    # occurrences touch it, so a later re-match could land on a different
    # region than the one originally incremented, corrupting an unrelated
    # region's bookkeeping. Never read to decide any *new* admission
    # decision -- only ever consulted to reverse this row's own, already-
    # made contribution.
    scene_confusor_region_id: Mapped[str | None] = mapped_column(String, nullable=True)


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


class ResearchCollectionModel(Base):
    """A named, bounded research/dataset collection (Research/Conservation/
    Export Interoperability v1, schema 42; see docs/research-conservation-
    export-contract.md "Collection/contributor model"). Mirrors
    `DatasetExportModel`'s own bounded `selected_visit_ids_json` shape --
    membership is an explicit, capped list a user assembles, never an
    implicit "everything reviewed" set and never a second parallel truth
    store: every included id is still resolved through the ordinary Visit/
    ReviewLabel truth boundary at export time, not cached here.

    `curator_identity` mirrors `ReviewLabelModel.reviewer_identity`'s own
    established free-text "who/what" convention (there is no user/account
    system in this product -- see review_provenance.py): who assembled this
    collection, never a taxonomic reviewer and never review authority (see
    "Contributor authority" in the governing milestone brief).
    `eligibility_policy_version` is recorded at creation time so a later
    export of this same collection can disclose whether the eligibility
    policy has since changed (see "Research replication / dataset identity"
    in the governing brief).
    """

    __tablename__ = "research_collections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    curator_identity: Mapped[str | None] = mapped_column(String, nullable=True)
    visit_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    eligibility_policy_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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


class CameraOnvifProfileModel(Base):
    """v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.4 ONVIF",
    "II.20 provenance bridge"): the bounded, per-Source record of which
    ONVIF device/media profile a `provider_key="external_url"` RTSP Source
    was actually configured through, kept only so the product can honestly
    say "connected via ONVIF" and let a user re-discover/re-select a
    profile later -- never itself the source of playback truth (the
    `SourceProviderConfigurationModel` row's own `live_stream_url`/
    `live_stream_type="rtsp"` is, exactly like a manually-entered RTSP
    camera; see mockingbird.source_providers.onvif_client's module
    docstring). One row per Source: a Source not configured through ONVIF
    simply has none.

    `onvif_credential` is kept exactly the way every other completed
    Source credential already is (plain local SQLite -- this product's
    existing trust boundary; see `CameraNodePendingSetupModel`'s identical
    precedent) -- never returned by any API response and never logged.
    `device_manufacturer`/`device_model`/`device_firmware_version` and
    `advertised_width`/`advertised_height` are the camera's own
    self-reported, unverified identity/capability claims (ONVIF
    GetDeviceInformation/GetProfiles) -- informational display only, never
    presented as verified/observed facts (see "II.15 Source-resolution
    evidence": only what the RTSP bridge actually receives is
    authoritative resolution).
    """

    __tablename__ = "camera_onvif_profiles"

    source_id: Mapped[str] = mapped_column(ForeignKey("camera_sources.id"), primary_key=True)
    onvif_host: Mapped[str] = mapped_column(String, nullable=False)
    onvif_port: Mapped[int] = mapped_column(Integer, nullable=False)
    onvif_username: Mapped[str | None] = mapped_column(String, nullable=True)
    onvif_credential: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_token: Mapped[str] = mapped_column(String, nullable=False)
    profile_name: Mapped[str | None] = mapped_column(String, nullable=True)
    device_manufacturer: Mapped[str | None] = mapped_column(String, nullable=True)
    device_model: Mapped[str | None] = mapped_column(String, nullable=True)
    device_firmware_version: Mapped[str | None] = mapped_column(String, nullable=True)
    advertised_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    advertised_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserModel(Base):
    """Local Identity, Multi-User & Organization Access v1 (schema 50; see
    docs/local-identity-multi-user-contract.md): a durable local human
    account on this one Host. This is the first identity/account table in
    the product -- deliberately small (`mockingbird.api.auth.Role` is a
    3-value ladder: viewer < reviewer < administrator) and deliberately
    local-only (no LDAP/OIDC/cloud-account fields; see the governing
    milestone's explicit exclusion list).

    `password_hash` is never plaintext and never reversible -- see
    `mockingbird.security.passwords` (stdlib `hashlib.scrypt`, RFC 7914; no
    new third-party dependency, matching this project's demonstrated
    aversion to fragile compiled-wheel closures for its packaged Windows
    build). The stored string is self-describing
    (`"scrypt$n=..,r=..,p=.."$<salt_hex>$<hash_hex>`) so a future algorithm
    change can recognize and re-hash old rows on next successful login
    without a schema migration.

    `login_identity` is stored lowercase-normalized (a local username, not
    necessarily an email) and is the sign-in handle; `display_name` is the
    human-facing name shown in review provenance and audit entries and may
    be re-cased/changed freely without affecting sign-in.

    `enabled=False` must make every *current and future* request for that
    user unauthorized on its very next check -- this table is looked up
    fresh on every session resolution (see
    `mockingbird.api.auth.resolve_session`), so disabling a user needs no
    separate session-revocation sweep to take effect immediately.

    `password_updated_at` is an informational record of when the password
    was last changed. It is deliberately NOT cross-checked against
    `UserSessionModel.created_at` during session resolution: doing so
    would also invalidate the one session a self-service password change
    deliberately preserves (see `ProductRepository.change_own_password`
    and `.resolve_session`'s own docstring for the full reasoning) --
    every session that should stop working after a password change is
    instead revoked explicitly and individually, which is the real
    enforcement mechanism.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("login_identity", name="uq_users_login_identity"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    login_identity: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    password_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserSessionModel(Base):
    """A durable, server-side authenticated session (Local Identity, Multi-
    User & Organization Access v1, schema 50). Deliberately opaque-server-
    side rather than a signed/JWT-style client-held session: the browser
    cookie carries only a high-entropy random token
    (`secrets.token_urlsafe(32)`); this table stores only
    `hashlib.sha256(token).hexdigest()`, never the raw token, mirroring how
    `password_hash` never stores a plaintext password -- a stolen database
    backup cannot be replayed as a live session cookie.

    Choosing server-side sessions over a self-contained token is what lets
    `UserModel.enabled` and `.role` changes take effect immediately (the
    very next request re-reads the live `User` row via `user_id`) with no
    separate revocation/blocklist machinery -- see `UserModel`'s own
    docstring.

    `revoked_at` is set (never a hard row delete) on explicit sign-out and
    on every session belonging to a user whose password just changed --
    "honest absence" (`NULL` = never revoked), the same convention this
    codebase already uses for `camera_node_identity_replaced_at` and
    similar bolt-on lifecycle columns. `expires_at` is a plain rolling
    absolute expiry, extended (throttled -- see `resolve_session`) on use;
    there is no separate idle-vs-absolute cap, kept deliberately simple for
    a local single-Host product (see "Local network security guidance" in
    the governing milestone brief).
    """

    __tablename__ = "user_sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLogEntryModel(Base):
    """A generic, append-only audit trail row (Local Identity, Multi-User &
    Organization Access v1, schema 50). This is a genuine first-of-its-kind
    table for this codebase: existing "provenance" precedents
    (`camera_configuration_revisions`, `ReviewLabelModel`'s own lineage
    columns, the boot-identity/replacement columns bolted onto
    `camera_sources`) are each one dedicated table or bolt-on column per
    feature, not a cross-cutting log -- see docs/local-identity-multi-user-
    contract.md "Audit trail" for why a generic table was still the right
    shape here (many distinct action families, each needing the same
    actor/target/timestamp shape, none needing unbounded per-feature
    growth).

    Deliberately narrow and deliberately *not* comprehensive: only the
    material, human-initiated mutations the governing milestone brief
    names explicitly are ever written here (user/role/camera/privacy/
    retention/backup/review actions) -- never page views, GETs, or routine
    inference activity. `metadata_json` is a small, hand-picked, bounded
    structured blob per action (e.g. `{"previous_role": ..., "new_role":
    ...}`) -- deliberately never a raw request-body dump, so a secret
    (password, session token, camera credential) can never reach this
    table by accident the way it could through a generic "log everything"
    writer. `target_type`/`target_id` mirror `ReviewLabelModel`'s existing
    polymorphic-target pair rather than inventing a new convention.

    `actor_display_name` is a point-in-time snapshot, not a live join to
    `UserModel.display_name` -- so a later rename (or the user being
    disabled) never rewrites how past audit history reads, matching this
    codebase's established "never retroactively rewrite history" doctrine
    for reviewed truth.
    """

    __tablename__ = "audit_log_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)


class InstallationSettingsModel(Base):
    """One durable installation-level identity record (Local Identity,
    Multi-User & Organization Access v1, schema 50) -- the exact
    `singleton_id`-primary-key idiom already established by
    `AppSetupStateModel`/`StorageRetentionSettingsModel`. Deliberately
    lightweight display metadata only, never an `Organization` tenancy
    table: one Host remains one deployment/security boundary (see the
    governing milestone brief's "Organization metadata" section) -- there
    is exactly one row, ever.
    """

    __tablename__ = "installation_settings"

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    installation_name: Mapped[str | None] = mapped_column(String, nullable=True)
    organization_name: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_display: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FieldAcceptanceCredentialModel(Base):
    """A narrow, explicitly-provisioned, non-interactive credential (Non-
    Interactive Field Acceptance Authentication & Session Access v1, schema
    58; see docs/non-interactive-field-acceptance-authentication-session-
    access-v1-contract.md) that lets bounded field-acceptance tooling
    authenticate to this one Host without sharing a human Administrator's
    password and without a second, weaker auth stack.

    Deliberately **not** a `UserModel` row and **not** a `role` value on the
    existing Viewer < Reviewer < Administrator ladder: the acceptance
    workflow's required permission shape (broad read access, plus exactly
    two otherwise-Administrator-tier mutations -- Observation start/stop --
    and nothing else Administrator-tier) is not a contiguous prefix of that
    ladder, so no single rank placement could express it without either
    under- or over-granting. This table is instead a second, parallel,
    narrow identity system, mirroring this codebase's own established
    precedent for exactly this shape: Camera Node device identity is
    already a completely separate mechanism from human `UserModel` identity
    (see docs/local-identity-multi-user-contract.md "Camera Node identity
    separation"). See `mockingbird.api.auth`'s `FIELD_ACCEPTANCE_ALLOWED_
    ADMIN_ROUTES`/`_authorize` for the exact, small, explicit allowlist this
    identity is checked against.

    `token_hash` follows `UserSessionModel.token_hash`'s exact convention --
    only `hashlib.sha256(token).hexdigest()` is ever persisted, via the same
    `generate_session_token`/`hash_session_token` helpers
    (`mockingbird.security.passwords`) sessions already use; a stolen
    database backup cannot be replayed as a live bearer credential. Unlike a
    human session, `expires_at` is **not nullable** -- every credential this
    table can ever hold is bounded by construction (no "permanent" path
    exists at all in v1; see the governing contract's "Credential lifecycle"
    for why this is a deliberately stricter default than the brief's own
    minimum bar). `revoked_at` mirrors `UserSessionModel.revoked_at`'s exact
    "honest absence" convention (`NULL` = never revoked, set once on
    explicit revoke, never a hard row delete) -- revocation must be
    immediate and deterministic, and `resolve_field_acceptance_token`
    re-reads this row fresh on every single call (no cache, no blocklist
    sweep needed), exactly like `resolve_session` does for `UserModel`.

    `created_by_user_id`/`created_by_display_name` mirror `AuditLogEntry
    Model.actor_user_id`/`.actor_display_name`'s point-in-time-snapshot
    convention -- which Administrator provisioned this credential, captured
    at creation time so a later rename/disable never rewrites how past
    provisioning history reads.
    """

    __tablename__ = "field_acceptance_credentials"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_field_acceptance_credentials_token_hash"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EnvironmentalContextSettingsModel(Base):
    """One durable, opt-in Place-level location setting (Environmental
    Context Foundation v1, schema 51) -- the same `singleton_id`-primary-key
    idiom as `InstallationSettingsModel`/`StorageRetentionSettingsModel`/
    `AppSetupStateModel`: exactly one row, ever. Kept as its own table
    rather than added to `InstallationSettingsModel`, whose own docstring
    scopes it to "lightweight display metadata only" -- a geographic
    setting used for local environmental computation is a different
    concern.

    `coarse_latitude`/`coarse_longitude` are a deliberate, narrow exception
    to the "no persisted site/coordinate model" invariant in
    docs/research-conservation-export-contract.md "Privacy" -- see
    docs/environmental-context-foundation-v1-contract.md "Place
    coordinates: a deliberate, narrow exception..." for the full
    reasoning. Always rounded to one decimal degree (~11 km) before being
    written -- the column names encode that contract permanently, not just
    a comment, so a future reader cannot mistake this for a precise
    location. Both are nullable and default absent: the entire
    Environmental Context feature must remain optional and absence-safe.
    Never read by, or written from, `CamtrapDpExportRequest.latitude`/
    `.longitude` or `RecordedAudioAnalysisRequest.latitude`/`.longitude`,
    which remain explicit-per-call-only and untouched by this milestone.

    `weather_enabled` (Environmental Context v2, schema 54): a second,
    independent opt-in gate, deliberately separate from
    `coarse_latitude`/`coarse_longitude` being set. Configuring coordinates
    enables only local, offline solar/daylight computation (`solar_local`,
    zero network access); `weather_enabled` is the explicit, separate
    consent required before this installation ever sends that coordinate
    to an external weather provider (`open_meteo`) over the network -- see
    docs/environmental-context-v2-contract.md "Phase 16" /
    "Privacy / location". `NOT NULL DEFAULT 0`: an upgraded installation
    that already has a location configured for solar does not silently
    start making outbound weather requests.
    """

    __tablename__ = "environmental_context_settings"

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coarse_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    coarse_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EnvironmentalContextRecordModel(Base):
    """One durable environmental-context fact (Environmental Context
    Foundation v1, schema 51) -- see docs/environmental-context-
    foundation-v1-contract.md "Data model" for the full field-by-field
    rationale. Provider-neutral: v1's only writer is the local solar
    provider (`provider_key="solar_local"`, `information_class="inferred"`,
    `metric` in `("sunrise", "sunset")`) -- solar geometry is computed
    deterministically from Place coordinates and a UTC instant via a
    documented algorithm, not read from a physical sensor, so it is
    doctrine's "Inferred" tier, not "Measured," despite being repeatable
    (see "Measured, Inferred, and Reviewed" in product-doctrine.md).
    `information_class` stays within that same closed three-value
    doctrine vocabulary used everywhere else in this product: every column
    is shaped to support a future locally-attached sensor reading a real
    physical quantity (`information_class="measured"`) or a future public
    weather/environmental API (`information_class="measured"` or
    `"inferred"`, depending on what that provider actually represents)
    without a schema change -- but *which* provider produced a record is
    `provider_key`'s job, never a new `information_class` value; identity
    and epistemic tier are deliberately two separate columns (see
    docs/environmental-context-foundation-v1-contract.md "Information
    class / provenance").

    `source_id` is nullable: `NULL` means "applies to the whole Place" (no
    `PlaceModel` exists -- see "Spatial doctrine" in product-doctrine.md
    and camera-source-multi-camera-maturity-v1-contract.md's "Place:
    unchanged" note), the only case v1 ever writes. A non-null value scopes
    a record to one Source, for a future per-camera sensor.

    `value_numeric`/`value_text`/`unit` are all `NULL` for v1's
    instant-valued metrics -- for `sunrise`/`sunset`, `observed_at` alone
    carries the fact. They exist for a future numeric metric (e.g.
    temperature would populate `value_numeric`/`unit`) or categorical one,
    without a schema change.

    `observed_at_end` is nullable and unused by v1 (sunrise/sunset are
    instants, not intervals); its presence lets a future daily
    min/max-style aggregate express an interval without a schema change.

    `for_date` is the *UTC calendar date* passed to `astral.sun.sun` as
    `date` (with `tzinfo=timezone.utc`) to produce this row -- see
    `mockingbird.environment.solar_context.compute_daily_solar_facts` --
    never a claim about this record's `basis_latitude`/`basis_longitude`'s
    local/civil date (see "Solar temporal semantics acceptance closure" in
    docs/environmental-context-foundation-v1-contract.md for a real,
    corrected mistake this milestone first made in exactly that
    direction). `NULL` for a future metric with no natural single day.
    `for_date` is the lookup key so a query is a plain equality match, not
    a re-derivation from `observed_at` -- but one row's own `for_date`
    does not by itself imply a coherent [sunrise, sunset) window (see
    `solar_context.find_daylight_window` for how a real window is
    constructed from one or more of these rows).

    `basis_latitude`/`basis_longitude` snapshot the coordinates actually
    used to compute this one record, independent of the live
    `EnvironmentalContextSettingsModel` value, so a record stays
    self-describing even after the user edits their configured location.

    `provenance_json` is one small, fixed-shape, bounded JSON object
    (algorithm name/version, twilight definition used) -- never a raw
    provider-response dump, extending `AuditLogEntryModel.metadata_json`'s
    "never a raw request-body dump" discipline to "never a raw
    provider-response dump" so a future external provider cannot leak an
    API key or unbounded payload here by accident.
    `provenance_schema_version` (matching `BioClipIdentificationAttemptModel`'s
    identical column) lets that JSON shape evolve later without a table
    migration.

    Idempotency note: a DB `UNIQUE` constraint spanning nullable
    `source_id` would not actually de-duplicate Place-level rows (SQLite,
    like standard SQL, treats every `NULL` as distinct from every other
    `NULL` in a unique index) -- so "one sunrise/sunset per calendar day"
    is enforced at the repository layer (check-then-insert-or-reuse), not
    here. Consumers should tolerate a rare duplicate row for the same day
    and prefer the most recently created one.
    """

    __tablename__ = "environmental_context_records"
    __table_args__ = (
        CheckConstraint(
            "provenance_schema_version >= 1",
            name="ck_environmental_context_record_provenance_version",
        ),
        Index(
            "ix_environmental_context_records_lookup",
            "source_id",
            "provider_key",
            "metric",
            "for_date",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("camera_sources.id"), nullable=True
    )
    provider_key: Mapped[str] = mapped_column(String, nullable=False)
    information_class: Mapped[str] = mapped_column(String, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    for_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    basis_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    basis_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlaceHabitatFactModel(Base):
    """One durable, user-recorded Place habitat fact (Habitat & Phenology
    Foundation v1, schema 52) -- see docs/habitat-phenology-foundation-v1-
    contract.md "Data model". A flexible, open-vocabulary tag/fact model
    (per the governing brief's "prefer a flexible controlled-vocabulary/
    tag/fact model over dozens of schema columns"), not a growing set of
    boolean columns: "does this Place have a water feature" is one row
    with `category="feature"`, `label="Water feature"`, not a
    `has_water_feature` column, so a future new habitat concept needs no
    migration.

    `category` is a genuinely closed, small set (`"setting"`,
    `"vegetation"`, `"feature"` -- see `mockingbird.habitat.phenology.
    HABITAT_FACT_CATEGORIES`) validated at the Pydantic/API layer as a
    `Literal`, not a DB `CHECK` -- matching house style for other
    string-vocabulary columns (`zone_type`, `information_class`).
    `label` stays free text on purpose: the UI offers a curated suggestion
    list per category, but a user is never blocked from recording
    something the suggestion list did not anticipate (see "Free-text/
    common-name subject labels are acceptable for v1" in the governing
    brief, applied here to habitat labels as well as phenology subjects).

    Absence of a row for some category/label is never itself evidence of
    anything -- there is no "confirmed absent" state, only "not recorded."
    Every reader (API and UI alike) must present a sparse/empty result as
    "nothing recorded yet," never as "this Place lacks X" -- the governing
    brief's "users must be able to record 'unknown/not specified'; absence
    of a fact must not imply false," satisfied here by never manufacturing
    a negative claim rather than by adding an explicit "not present" row
    for every conceivable category.

    `source_id` is nullable, `NULL` = Place-wide (no `PlaceModel` exists --
    see "Spatial doctrine" in product-doctrine.md); the only case v1 ever
    writes. Mirrors `EnvironmentalContextRecordModel.source_id` exactly,
    reserved for a future per-camera habitat-scene association without a
    schema change.

    `information_class`/`provenance` mirror `EnvironmentalContextRecordModel.
    information_class`/`provider_key`'s two-column split (what epistemic
    tier vs. what specific method produced it): v1's only writer is a
    human directly describing their own Place, which is exactly doctrine's
    "reviewed" tier ("human-validated semantic truth" in "Measured,
    Inferred, and Reviewed" in product-doctrine.md) -- so
    `information_class="reviewed"` and `provenance="user_manual_entry"`.
    `information_class` stays within that same closed three-value
    doctrine vocabulary used everywhere else in this product; it never
    grows a fourth, domain-specific value for "who/what produced this
    fact" -- authorship/source belongs entirely to `provenance`, epistemic
    tier to `information_class`. Both stay plain strings, not growing
    enums: `provenance` reserves room for a future distinct writer (an
    imported ecological dataset), and `information_class` already has a
    legal home for a future automatic plant-recognition analyzer's output
    (`"inferred"`, doctrine's own "possible flowering onset" example)
    without inventing anything new -- see "Future compatibility" in
    docs/habitat-phenology-foundation-v1-contract.md. Using `"reviewed"`
    here does not create or alter a wildlife `ReviewLabel`, does not
    create reviewed wildlife species truth, and does not touch Observation
    review authority: it is the same epistemic tier as wildlife Reviewed
    truth (a person deliberately supplied/reviewed this fact), never the
    same table or mechanism. No separate "review state" column: nothing
    here is a machine proposal awaiting human confirmation, so
    `information_class="reviewed"` plus `provenance="user_manual_entry"`
    already says precisely what this is without importing
    `ReviewLabel`/`reviewed_by_user_id` machinery this feature does not
    use.
    """

    __tablename__ = "place_habitat_facts"
    __table_args__ = (
        Index("ix_place_habitat_facts_lookup", "source_id", "category"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("camera_sources.id"), nullable=True
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    information_class: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlacePhenologyObservationModel(Base):
    """One dated/interval Place phenology observation (Habitat & Phenology
    Foundation v1, schema 52) -- see docs/habitat-phenology-foundation-v1-
    contract.md "Data model". Distinct from `PlaceHabitatFactModel`: a
    habitat fact is durable/open-ended ("this Place has mature deciduous
    trees"), a phenology observation is explicitly time-bounded ("azaleas
    were flowering here"). Do not assume every row is a plant species
    identification -- `subject_label` is free text (a common name, a
    resource description like "sunflower feeder," or anything else a user
    types), matching "Free-text/common-name subject labels are acceptable
    for v1" in the governing brief.

    `observed_start_date`/`observed_end_date` are plain `date` values, not
    `datetime` instants -- a phenology entry is a human-entered,
    day-granularity fact, and storing a fabricated time-of-day would
    overclaim precision that was never observed (see "Be precise" in the
    governing brief's "Temporal semantics"). `observed_end_date=NULL`
    means a single-date observation, exactly equivalent to
    `observed_end_date == observed_start_date` for every "is this
    currently applicable" purpose -- it never means "ongoing
    indefinitely." This is the specific, deliberate mechanism that keeps
    an April observation from silently still reading as current in
    August: without an explicit end date extending it, a single-date
    entry's own "current" window is exactly the one day it was recorded
    for. See `mockingbird.habitat.phenology.phenology_interval_covers`/
    `classify_phenology_status` for the read-time classification logic --
    "current"/"recent"/"past" is never persisted here, mirroring
    `EnvironmentalContextRecordModel`'s own "day/night classification is
    never persisted per-Visit, always re-derived at read time" discipline,
    applied to phenology's own date-range shape instead of an instant
    window.

    `source_id`/`information_class`/`provenance` mirror
    `PlaceHabitatFactModel`'s identical fields and reasoning exactly (see
    that model's docstring) -- `source_id` nullable/Place-wide-only for
    v1, `information_class="reviewed"`,
    `provenance="user_manual_entry"`.
    """

    __tablename__ = "place_phenology_observations"
    __table_args__ = (
        CheckConstraint(
            "observed_end_date IS NULL OR observed_end_date >= observed_start_date",
            name="ck_place_phenology_observation_end_not_before_start",
        ),
        Index(
            "ix_place_phenology_observations_lookup", "source_id", "observed_start_date"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("camera_sources.id"), nullable=True
    )
    subject_label: Mapped[str] = mapped_column(String, nullable=False)
    phenomenon: Mapped[str] = mapped_column(String, nullable=False)
    information_class: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)
    observed_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlaceFeatureModel(Base):
    """One durable, user-recorded Place Feature (Place Features & Habitat
    Change v2, schema 55) -- see docs/place-features-habitat-change-v2-
    contract.md "Data model". Distinct from `PlaceHabitatFactModel`: a
    Feature has its own durable identity and lifecycle -- "the sunflower
    feeder" can be referred to, associated with a camera, and have activity
    computed for it as one thing over time, rather than being re-described
    as a fresh, untracked tag fact on every mention. `mockingbird.habitat.
    place_feature` owns the closed `feature_type` vocabulary
    (`PLACE_FEATURE_TYPES`), validated as a `Literal` at the API layer, not
    a DB `CHECK` -- matching house style for every other string-vocabulary
    column in this product (`zone_type`, `category`).

    This row holds *current* state only -- the durable, append-only
    timeline of what happened to this Feature over time lives entirely in
    `PlaceFeatureChangeEventModel` rows referencing this `id`; this is a
    deliberate dual-write, not event sourcing (see that model's docstring,
    "Feature state vs change history" in the contract doc, and Phase 5 of
    the governing brief). `is_active`/`removed_date` may be set two ways:
    directly, via an ordinary edit (a lightweight, reversible toggle -- "I
    temporarily marked this inactive"); or as a side effect, in the same
    transaction, of recording a `event_type="removed"` change event (the
    dated, historically-significant "this was actually decommissioned on
    date X" fact). Recording (or later deleting) a `food_changed` event
    similarly keeps `feeder_food_type` current -- see
    `mockingbird.habitat.place_feature.DERIVED_STATE_EVENT_TYPES`.

    `source_id`/`zone_id` are both nullable and independent of each other:
    `NULL`/`NULL` means "Place knowledge only, no camera association" (a
    Feature may exist without ever being watched by a camera -- Phase 6 of
    the governing brief). `zone_id` is the finer-grained, preferred
    association when a Zone already exists for this Feature (mirrors
    `VisitModel.zone_id`/`DetectionModel.zone_id`'s identical nullable-FK
    idiom); `source_id` is coarser ("which camera," with no specific Zone
    drawn yet) and, when `zone_id` is also set, is kept consistent with
    that Zone's own Stream's Source by the repository layer rather than
    trusted independently from a client payload.

    Multi-Camera Place Feature Linking & Cross-View Habitat Context v1
    (schema 59) lifted the prior "at most one Zone/Source" limitation this
    docstring used to document (Phase 28 of Place Features & Habitat
    Change v2's own brief): the canonical, possibly-plural relationship
    set now lives in `PlaceFeatureObservationLinkModel`, one row per
    linked camera/Zone view, referencing this row's own `id` by
    `feature_id`. **These two columns remain on this row as a
    repository-maintained compatibility mirror, not the source of
    truth**: `ProductRepository` keeps them equal to the Feature's own
    single link's `(source_id, zone_id)` pair whenever it has exactly one
    observation link, and resets both to `NULL` whenever it has zero or
    two-or-more links -- an honest absence rather than an arbitrarily
    "first" link standing in for a set, matching this codebase's own
    abstention discipline (see docs/product-doctrine.md "Measured,
    Inferred, and Reviewed"). Existing callers reading these two columns
    directly (`_place_story_feature_events`'s own per-event `zone_id`/
    `source_id` projection) therefore continue to work unmodified: a
    migrated single-link Feature reads back exactly as before, and a
    genuinely multi-link Feature honestly reports "no single camera/Zone"
    on this row rather than an arbitrary one. See
    `PlaceFeatureObservationLinkModel`'s own docstring for the canonical
    relationship shape, and
    docs/multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md
    for the full contract.

    `feeder_food_type` is a small, bounded, feeder-specific field (Phase 8
    of the governing brief) -- meaningless but harmless for a non-feeder
    `feature_type`; no DB constraint ties the two together, matching this
    codebase's "flexible tag, not dozens of enforced columns" house style.
    This is deliberately not an inventory system: no purchase receipts, no
    exact food weight, no SKUs, no supply forecasting.

    `information_class`/`provenance` mirror `PlaceHabitatFactModel`'s
    identical two-column split and v1-only values (`"reviewed"`/
    `"user_manual_entry"`) exactly -- a human directly describing their own
    Place is doctrine's own "human-validated semantic truth" tier. Unlike
    that precedent, this model *also* carries `actor_user_id` directly on
    the row (not only in the generic audit log): the governing brief
    explicitly requires durable, on-row "reviewed actor provenance" for
    both this model and `PlaceFeatureChangeEventModel`, so this deliberately
    goes one step further than the Habitat & Phenology v1 precedent,
    reusing `ReviewLabelModel.reviewed_by_user_id`'s exact nullable-FK
    idiom instead: populated only by the authenticated HTTP handler from
    the signed-in session, never trusted from a client-supplied payload
    field, and `NULL` for any row created by a future non-interactive
    pathway that has no signed-in user.
    """

    __tablename__ = "place_features"
    __table_args__ = (
        Index("ix_place_features_source_active", "source_id", "is_active"),
        Index("ix_place_features_zone", "zone_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    feature_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    installed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    removed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("camera_sources.id"), nullable=True
    )
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    feeder_food_type: Mapped[str | None] = mapped_column(String, nullable=True)
    information_class: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlaceFeatureChangeEventModel(Base):
    """One durable, user-recorded, dated fact about something that changed
    around the Place (Place Features & Habitat Change v2, schema 55) -- see
    docs/place-features-habitat-change-v2-contract.md "Data model". This is
    the discrete before/after *change-event* concept confirmed absent
    everywhere else in this codebase before this milestone (see
    `mockingbird.analytics.habitat_association`'s own docstring, which
    names this exact gap) -- distinct from `PlacePhenologyObservationModel`,
    which describes a *recurring biological phenomenon* with a start/end
    interval ("azaleas flowering"), not a discrete one-time change ("planted
    the azaleas").

    `feature_id` is nullable on purpose: most events describe something
    that happened to one tracked `PlaceFeatureModel`, but a Place-level
    habitat change with no specific tracked Feature ("changed mowing
    practice") can still be recorded as a Reviewed fact without inventing a
    Feature row it does not really need. `mockingbird.habitat.place_feature`
    owns the closed `event_type` vocabulary
    (`PLACE_FEATURE_CHANGE_EVENT_TYPES`), validated as a `Literal` at the
    API layer.

    `effective_date` is a plain `date`, never `datetime` -- mirrors
    `PlacePhenologyObservationModel.observed_start_date`'s identical
    "human-entered, day-granularity fact; a fabricated time-of-day would
    overclaim precision that was never observed" discipline ("I added it
    around March 15," not a claimed instant).

    `prior_value`/`new_value` are a small, bounded, free-text pair -- not a
    polymorphic JSON blob -- satisfying the governing brief's "prior/new
    state metadata only if current architecture supports it cleanly"
    without over-building. For `event_type="food_changed"`, `new_value` is
    also what the repository copies into the referenced Feature's own
    `feeder_food_type` (see `PlaceFeatureModel`'s docstring); for every
    other event type both columns are purely descriptive and never read by
    any dual-write.

    Correction model: this row is PATCH-corrected in place (mirroring
    `PlacePhenologyObservationModel`'s identical precedent), not append-
    only-superseding the way wildlife `ReviewLabel` truth is. This is a
    deliberate, considered choice, not an oversight: `PlaceHabitatFactModel`
    /`PlacePhenologyObservationModel` already establish that this whole
    domain family avoids `ReviewLabel`/`reviewed_by_user_id`-style
    append-only machinery, and every derived comparison this milestone
    builds (`mockingbird.analytics.feature_change_comparison`) is computed
    fresh at read time from current rows, never cached -- so a correction
    here is automatically reflected on the very next read, with no
    invalidation step to get wrong, and no separate "correction history" UI
    is needed for a fact at this epistemic weight (see "Information class"
    in the contract doc). Deleting a row here is likewise an ordinary,
    always-available correction (Phase 22 of the governing brief), not a
    restricted operation the way hard-deleting a `PlaceFeatureModel` with
    existing history is.

    `information_class`/`provenance`/`actor_user_id` mirror
    `PlaceFeatureModel`'s identical fields and reasoning exactly.
    """

    __tablename__ = "place_feature_change_events"
    __table_args__ = (
        Index(
            "ix_place_feature_change_events_feature_date", "feature_id", "effective_date"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    feature_id: Mapped[str | None] = mapped_column(
        ForeignKey("place_features.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    prior_value: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value: Mapped[str | None] = mapped_column(String, nullable=True)
    information_class: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlaceFeatureObservationLinkModel(Base):
    """One camera/Zone observation view of a Place Feature (Multi-Camera
    Place Feature Linking & Cross-View Habitat Context v1, schema 59) --
    see docs/multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md
    "Observation-link contract". This is the canonical, possibly-plural
    relationship set `PlaceFeatureModel`'s own `source_id`/`zone_id`
    columns used to hold directly, singular-only, before this milestone
    (see that model's docstring). "These cameras are different views of
    the same thing," not "each camera has its own duplicate feeder" --
    the Feature's own identity/lifecycle stays entirely on
    `PlaceFeatureModel`; this table only ever adds or removes a *view* of
    it, never a second Feature.

    Column choice: `source_id` (not `stream_id`), deliberately matching
    `PlaceFeatureModel.source_id`'s own existing FK target exactly, rather
    than mechanically adopting the governing brief's own candidate schema's
    literal naming. `zone_id` is the finer-grained, optional refinement,
    exactly mirroring `PlaceFeatureModel`'s existing
    two-column idiom and `ProductRepository._resolve_feature_association`'s
    existing zone-authoritative-over-source validation, reapplied per
    link instead of once per Feature. This keeps a migrated single-link
    Feature's one backfilled row byte-identical in shape to what
    `PlaceFeatureModel` already stored, and needs no lossy or ambiguous
    Source-to-Stream translation during migration.

    Duplicate prevention: a plain multi-column `UniqueConstraint`
    spanning the nullable `zone_id` would not actually work -- SQLite,
    like standard SQL, treats every `NULL` as distinct from every other
    `NULL` in a unique index (see `EnvironmentalContextRecordModel`'s own
    docstring, which documents this exact pitfall). Two partial unique
    indexes cover both cases instead (mirroring the nullable-column
    partial-index idiom `SpeciesSuggestionModel`'s own acoustic-
    idempotency index already established): one for a real Zone-scoped
    link, one for a bare Source-scoped link. Backstopped, not replaced,
    by an app-level `.is_(None)`-aware existence check in the repository
    layer (the same "index is a backstop, the query is the real guard"
    convention that model's own commented index already uses) -- prevents
    the identical (feature, camera, Zone) view from being linked twice
    while allowing a Feature to hold two independent links against the
    very same Source (e.g. two different drawn Zones on one camera, both
    genuinely showing part of the same physical Feature).

    Reviewed truth: `information_class`/`provenance`/`actor_user_id`
    mirror `PlaceFeatureModel`'s identical fields and reasoning exactly --
    a human explicitly saying "this camera/Zone also shows this Feature"
    is the same "reviewed" epistemic tier as recording the Feature
    itself; model inference must never silently create or remove a row
    here (see docs/product-doctrine.md "Measured, Inferred, and
    Reviewed" and the governing brief's "No automatic physical-object
    inference"). No `updated_at`: a link is only ever added or removed,
    never edited in place, mirroring `VisitEvidenceLinkModel`'s identical
    "created_at only" precedent for the same reason.

    Deletion: removing a link is always allowed and never deletes the
    Feature, even when it is the Feature's only remaining link (Phase 15
    of the governing brief: an observation-link change describes
    monitoring configuration, never a physical habitat change, and must
    never be confused with `PlaceFeatureChangeEventModel`'s own durable,
    Reviewed change-event history). Conversely, hard-deleting a Feature
    itself (`ProductRepository.remove_place_feature`, blocked only by
    existing change-event history) cascades a bulk delete of this
    Feature's own link rows in the same transaction -- a link carries no
    historical weight of its own that would need `PlaceFeatureHasHistoryError`'s
    protection, so leaving them behind as orphans would be a pure defect,
    not a safety feature.
    """

    __tablename__ = "place_feature_observation_links"
    __table_args__ = (
        Index("ix_place_feature_observation_links_feature", "feature_id"),
        Index("ix_place_feature_observation_links_source", "source_id"),
        Index(
            "uq_place_feature_observation_links_zoned",
            "feature_id", "source_id", "zone_id",
            unique=True,
            sqlite_where=text("zone_id IS NOT NULL"),
        ),
        Index(
            "uq_place_feature_observation_links_unzoned",
            "feature_id", "source_id",
            unique=True,
            sqlite_where=text("zone_id IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    feature_id: Mapped[str] = mapped_column(ForeignKey("place_features.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("camera_sources.id"), nullable=False)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    information_class: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EcologicalTaxonomyMappingModel(Base):
    """Ecological Interoperability & Submission Workflows v1 (schema 57): a
    bounded, reusable cache of "MockingBird taxon label -> destination taxon"
    resolutions (see docs/ecological-interoperability-submission-v1-contract.md
    "Taxonomy translation"). Never mutates `TaxonomyLabelModel` -- this is a
    separate translation-layer fact, keyed by MockingBird's own stable taxon
    label, not a correction to local reviewed truth (product-doctrine.md "The
    truth boundary": a destination's taxonomy disagreeing never changes
    MockingBird's own label). `destination_taxon_id`/`destination_scientific_
    name`/`destination_display_name` are `None` whenever `match_status` is not
    `"matched"` -- an honest "not resolved," never a guessed value. One row
    per (destination, mockingbird_taxon_label); a destination's own taxonomy
    occasionally changes (a synonym, a split), so a fresh lookup replaces the
    existing row (`resolved_at` advances) rather than accumulating stale
    duplicates -- see "Taxonomy conflict" in the governing contract doc."""

    __tablename__ = "ecological_taxonomy_mappings"
    __table_args__ = (
        UniqueConstraint(
            "destination",
            "mockingbird_taxon_label",
            name="uq_ecological_taxonomy_mapping_destination_label",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    mockingbird_taxon_label: Mapped[str] = mapped_column(String, nullable=False)
    match_status: Mapped[str] = mapped_column(String, nullable=False)
    destination_taxon_id: Mapped[str | None] = mapped_column(String, nullable=True)
    destination_scientific_name: Mapped[str | None] = mapped_column(String, nullable=True)
    destination_display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    taxonomy_source_version: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[str] = mapped_column(String, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EcologicalSubmissionRecordModel(Base):
    """Ecological Interoperability & Submission Workflows v1 (schema 57): a
    durable per-Visit record of preparing -- and, only ever by explicit,
    after-the-fact self-report, never a live automated submit -- an external
    ecological submission for one Reviewed MockingBird Visit at one
    destination (see "Submission workflow state" in the governing contract
    doc). This never stores a destination credential/token (product-
    doctrine.md; "Authorization / secrets" in the governing brief):
    `external_id`/`external_url` are populated only from a value the *user*
    pastes back in after they submit the prepared record *themselves* through
    the destination's own site -- no adapter in this milestone performs a
    live submit (see the contract doc's "iNaturalist workflow"). `content_
    fingerprint` changes whenever the underlying Reviewed truth, taxonomy
    mapping, or the user's own location/media choices change; a stale
    fingerprint is the signal a previously-prepared package must be rebuilt
    before use (Phase 32 of the governing brief), never silently reused.
    Location/media fields are a snapshot of what the user explicitly chose at
    prepare time, never a silently-reused default (Phase 10/12) -- rebuilding
    after a correction re-asks rather than replaying the old choice."""

    __tablename__ = "ecological_submission_records"
    __table_args__ = (
        Index("ix_ecological_submission_records_visit_destination", "visit_id", "destination"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    taxon_label: Mapped[str | None] = mapped_column(String, nullable=True)
    taxon_scientific_name: Mapped[str | None] = mapped_column(String, nullable=True)
    destination_taxon_id: Mapped[str | None] = mapped_column(String, nullable=True)
    taxonomy_mapping_version: Mapped[str | None] = mapped_column(String, nullable=True)
    location_choice: Mapped[str] = mapped_column(String, nullable=False)
    location_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_place_name: Mapped[str | None] = mapped_column(String, nullable=True)
    media_selection_asset_id: Mapped[str | None] = mapped_column(String, nullable=True)
    media_policy: Mapped[str] = mapped_column(String, nullable=False)
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prepared_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String, nullable=True)
    result_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
