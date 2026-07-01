"""SQLAlchemy models for product-level MockingBird persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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
    source_id: Mapped[str] = mapped_column(ForeignKey("camera_sources.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ZoneModel(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    zone_type: Mapped[str] = mapped_column(String, nullable=False)
    polygon_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    primary_zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
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


class MediaAssetModel(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("camera_sources.id"), nullable=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str] = mapped_column(String, nullable=False)
    local_path: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DetectionRunModel(Base):
    __tablename__ = "detection_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    media_asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DetectionProposalModel(Base):
    __tablename__ = "detection_proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("detection_runs.id"), nullable=False)
    media_asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DatasetExportModel(Base):
    __tablename__ = "dataset_exports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    reviewed_only: Mapped[bool] = mapped_column(Boolean, nullable=False)
    include_detections: Mapped[bool] = mapped_column(Boolean, nullable=False)
    include_zone_context: Mapped[bool] = mapped_column(Boolean, nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
