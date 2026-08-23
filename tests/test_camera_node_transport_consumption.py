"""Tier 1/2: Appliance / Storage / Privacy / Recovery v1, Phase E -- the
Camera Node WAN-transport host-file consumer lifecycle.

Exercises `ProductRepository.consume_camera_node_transport_item`/
`consume_pending_camera_node_transport_backlog` directly against a real
`TransportLedger` rooted at an isolated `tmp_path` (never the process
default/env-resolved root) and a real, isolated SQLite database -- no HTTP,
no sockets (see tests/test_camera_node_transport_acceptance.py for the full
real-protocol proof; this file proves the *consumption* half that sits
downstream of a successful `complete()`).
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path

import pytest

from mockingbird.api.schemas import (
    CameraConfigurationImpactPreviewRequest,
    CameraConfigurationSecretAction,
    CameraSourceCreate,
    SourceProviderConfigurationUpdate,
)
from mockingbird.repository.product_repository import (
    CameraNodeTransportIngestionModel,
    ProductRepository,
)
from mockingbird.storage.camera_node_transport_ledger import TransportLedger
from mockingbird.storage.models import CameraSourceModel, MediaAssetModel


@pytest.fixture
def repository(tmp_path: Path):
    data_dir = tmp_path / "data"
    media_root = data_dir / "media" / "imports"
    media_root.mkdir(parents=True)
    repo = ProductRepository(db_url=f"sqlite:///{data_dir / 'mockingbird.sqlite3'}", media_root=media_root)
    try:
        yield repo
    finally:
        repo.close()


@pytest.fixture
def transport_root(tmp_path: Path) -> Path:
    return tmp_path / "camera_node_transport"


@pytest.fixture
def ledger(transport_root: Path) -> TransportLedger:
    return TransportLedger(transport_root)


def _pair_camera_node_source(
    repository: ProductRepository,
    *,
    name: str = "Yard Node",
    node_id: str = "node-abc123",
    transport_credential: str = "transport-credential-value",
) -> tuple[str, str]:
    created = repository.create_camera_source(CameraSourceCreate(name=name))
    repository.update_source_provider_configuration(
        created.source.id,
        SourceProviderConfigurationUpdate(
            provider_key="camera_node",
            config={
                "node_base_address": "http://192.168.1.50:8787",
                "node_credential": "pairing-credential-value",
                "node_transport_credential": transport_credential,
                "node_camera_id": "cam-1",
                "node_id": node_id,
                "node_pairing_state": "paired",
            },
        ),
    )
    return created.source.id, created.stream.id


def _complete_item(
    ledger: TransportLedger,
    *,
    node_id: str,
    item_id: str = "item-001",
    payload: bytes = b"jpeg-bytes-standing-in-for-a-real-frame",
    media_type: str = "image/jpeg",
    metadata: dict | None = None,
) -> str:
    content_sha256 = hashlib.sha256(payload).hexdigest()
    ledger.declare(
        node_id=node_id,
        item_id=item_id,
        kind="evidence_capture",
        priority=100,
        media_type=media_type,
        content_length=len(payload),
        content_sha256=content_sha256,
        chunk_size=65536,
        metadata=metadata or {},
    )
    ledger.write_chunk(
        node_id=node_id, item_id=item_id, chunk_index=0, chunk=payload, declared_sha256=content_sha256
    )
    ledger.complete(node_id=node_id, item_id=item_id)
    return content_sha256


def _ingestion_row(repository: ProductRepository, *, node_id: str, item_id: str):
    with repository.session_factory() as session:
        return session.query(CameraNodeTransportIngestionModel).filter_by(node_id=node_id, item_id=item_id).one_or_none()


def _media_asset_count(repository: ProductRepository) -> int:
    with repository.session_factory() as session:
        return session.query(MediaAssetModel).count()


# --------------------------------------------------------------------------
# Core ingestion
# --------------------------------------------------------------------------


def test_consume_ingests_a_completed_item_into_a_media_asset(repository, ledger, transport_root) -> None:
    source_id, stream_id = _pair_camera_node_source(repository)
    content_sha256 = _complete_item(
        ledger,
        node_id="node-abc123",
        metadata={"camera_id": "cam-1", "profile_id": "evidence-profile", "reason": "motion", "width": 1920, "height": 1080, "captured_at": "2026-08-23T12:00:00+00:00"},
    )

    status = repository.consume_camera_node_transport_item(node_id="node-abc123", item_id="item-001", transport_root=transport_root)

    assert status == "ingested"
    assert _media_asset_count(repository) == 1
    with repository.session_factory() as session:
        asset = session.query(MediaAssetModel).one()
        assert asset.source_id == source_id
        assert asset.stream_id == stream_id
        assert asset.media_type == "image"
        assert asset.content_type == "image/jpeg"
        assert asset.content_sha256 == content_sha256
        assert asset.image_width == 1920
        assert asset.image_height == 1080
        # SQLite has no native timezone-aware column type -- a round-tripped
        # value reads back naive but is still semantically UTC (the same
        # convention every other timestamp comparison in this suite uses).
        assert asset.captured_at.replace(tzinfo=UTC) == datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
        assert Path(asset.local_path).is_file()
        assert "node_id=node-abc123" in asset.notes
        assert "item_id=item-001" in asset.notes

    row = _ingestion_row(repository, node_id="node-abc123", item_id="item-001")
    assert row is not None
    assert row.status == "ingested"
    assert row.source_id == source_id
    assert row.media_asset_id is not None
    assert row.blob_deleted_at is not None

    # The transport ledger's own completed blob is now cleaned up -- the
    # sole surviving copy has moved into managed media storage.
    assert ledger.completed_blob_path("node-abc123", "item-001") is None


def test_consume_is_idempotent_on_a_second_call(repository, ledger, transport_root) -> None:
    _pair_camera_node_source(repository)
    _complete_item(ledger, node_id="node-abc123")

    first = repository.consume_camera_node_transport_item(node_id="node-abc123", item_id="item-001", transport_root=transport_root)
    second = repository.consume_camera_node_transport_item(node_id="node-abc123", item_id="item-001", transport_root=transport_root)

    assert first == "ingested"
    assert second == "ingested"
    assert _media_asset_count(repository) == 1


def test_consume_resumes_cleanly_after_a_simulated_crash_between_commit_and_blob_delete(
    repository, ledger, transport_root
) -> None:
    """Simulates a process killed after phase 1 (MediaAsset + ingestion row
    committed) but before phase 2 (blob deleted) -- the exact crash window
    `CameraNodeTransportIngestionModel.blob_deleted_at` exists to close."""

    source_id, stream_id = _pair_camera_node_source(repository)
    _complete_item(ledger, node_id="node-abc123")

    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id="media-asset-precommitted",
                    source_id=source_id,
                    stream_id=stream_id,
                    filename="precommitted.jpg",
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(repository.media_root / "precommitted.jpg"),
                    original_filename="precommitted.jpg",
                    file_size_bytes=10,
                    created_at=now,
                )
            )
            session.add(
                CameraNodeTransportIngestionModel(
                    id="transport-ingest-simulated",
                    node_id="node-abc123",
                    item_id="item-001",
                    source_id=source_id,
                    content_sha256="irrelevant-for-this-test",
                    content_length=10,
                    status="ingested",
                    media_asset_id="media-asset-precommitted",
                    attempt_count=1,
                    blob_deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
    (repository.media_root / "precommitted.jpg").write_bytes(b"x" * 10)
    assert ledger.completed_blob_path("node-abc123", "item-001") is not None  # still present, as after a real crash

    status = repository.consume_camera_node_transport_item(node_id="node-abc123", item_id="item-001", transport_root=transport_root)

    assert status == "ingested"
    assert _media_asset_count(repository) == 1  # never re-ingested as a second asset
    assert ledger.completed_blob_path("node-abc123", "item-001") is None
    row = _ingestion_row(repository, node_id="node-abc123", item_id="item-001")
    assert row.blob_deleted_at is not None


def test_consume_unattributed_source_leaves_blob_in_place_for_retry(repository, ledger, transport_root) -> None:
    # No camera_node Source configured anywhere that claims this node_id.
    _complete_item(ledger, node_id="node-unknown")

    status = repository.consume_camera_node_transport_item(node_id="node-unknown", item_id="item-001", transport_root=transport_root)

    assert status == "unattributed"
    assert _media_asset_count(repository) == 0
    row = _ingestion_row(repository, node_id="node-unknown", item_id="item-001")
    assert row.status == "failed"
    assert row.error_reason == "unattributed_source"
    # Cleanup must never delete data it could not attribute/consume.
    assert ledger.completed_blob_path("node-unknown", "item-001") is not None


def test_consume_resolves_attribution_via_prior_node_id_after_a_replacement(repository, ledger, transport_root) -> None:
    """A completed transport item can outlive a Camera Node hardware
    replacement -- it must still attribute to the same logical Source via
    `camera_node_prior_node_id`, not be orphaned."""

    source_id, _stream_id = _pair_camera_node_source(repository, node_id="node-new-hardware")
    with repository.session_factory() as session:
        with session.begin():
            source = session.get(CameraSourceModel, source_id)
            source.camera_node_prior_node_id = "node-old-hardware"
    _complete_item(ledger, node_id="node-old-hardware")

    status = repository.consume_camera_node_transport_item(
        node_id="node-old-hardware", item_id="item-001", transport_root=transport_root
    )

    assert status == "ingested"
    with repository.session_factory() as session:
        asset = session.query(MediaAssetModel).one()
        assert asset.source_id == source_id


def test_consume_content_hash_dedup_reuses_an_existing_media_asset(repository, ledger, transport_root) -> None:
    source_id, stream_id = _pair_camera_node_source(repository)
    payload = b"duplicate-bytes-already-imported-elsewhere"
    content_sha256 = hashlib.sha256(payload).hexdigest()
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id="media-asset-existing",
                    source_id=source_id,
                    stream_id=stream_id,
                    filename="existing.jpg",
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(repository.media_root / "existing.jpg"),
                    original_filename="existing.jpg",
                    file_size_bytes=len(payload),
                    created_at=now,
                    content_sha256=content_sha256,
                )
            )
    _complete_item(ledger, node_id="node-abc123", payload=payload)

    status = repository.consume_camera_node_transport_item(node_id="node-abc123", item_id="item-001", transport_root=transport_root)

    assert status == "ingested"
    assert _media_asset_count(repository) == 1  # no second MediaAsset created
    row = _ingestion_row(repository, node_id="node-abc123", item_id="item-001")
    assert row.media_asset_id == "media-asset-existing"
    assert ledger.completed_blob_path("node-abc123", "item-001") is None  # still cleaned up


def test_consume_unsupported_media_type_never_promotes_and_leaves_blob_in_place(
    repository, ledger, transport_root
) -> None:
    _pair_camera_node_source(repository)
    _complete_item(ledger, node_id="node-abc123", media_type="application/octet-stream")

    status = repository.consume_camera_node_transport_item(node_id="node-abc123", item_id="item-001", transport_root=transport_root)

    assert status == "pending_retry"
    assert _media_asset_count(repository) == 0
    row = _ingestion_row(repository, node_id="node-abc123", item_id="item-001")
    assert row.status == "failed"
    assert row.error_reason == "unsupported_media_type"
    assert ledger.completed_blob_path("node-abc123", "item-001") is not None


def test_consume_pending_backlog_sweeps_multiple_nodes(repository, ledger, transport_root) -> None:
    _pair_camera_node_source(repository, name="Node A", node_id="node-a")
    _pair_camera_node_source(repository, name="Node B", node_id="node-b")
    _complete_item(ledger, node_id="node-a", item_id="item-a1", payload=b"payload-a1")
    _complete_item(ledger, node_id="node-b", item_id="item-b1", payload=b"payload-b1")

    counts = repository.consume_pending_camera_node_transport_backlog(transport_root=transport_root)

    assert counts == {"ingested": 2}
    assert _media_asset_count(repository) == 2
    assert ledger.list_node_ids() == ["node-a", "node-b"]
    assert ledger.list_completed_item_ids("node-a") == []
    assert ledger.list_completed_item_ids("node-b") == []


def test_consume_pending_backlog_is_a_cheap_no_op_when_nothing_is_pending(repository, transport_root) -> None:
    counts = repository.consume_pending_camera_node_transport_backlog(transport_root=transport_root)
    assert counts == {}


# --------------------------------------------------------------------------
# Camera Node replacement / revocation bounded fixes (Phase I)
# --------------------------------------------------------------------------


def test_revoke_camera_node_pairing_also_clears_the_transport_credential(repository) -> None:
    source_id, stream_id = _pair_camera_node_source(repository, transport_credential="secret-transport-value")
    assert repository.resolve_camera_node_transport_source("secret-transport-value") == (source_id, "node-abc123")

    assert repository.revoke_camera_node_pairing(stream_id) is True

    assert repository.resolve_camera_node_transport_source("secret-transport-value") is None


def test_preview_camera_node_replacement_discloses_pending_transport_backlog(
    repository, monkeypatch
) -> None:
    from mockingbird.repository import product_repository as pr_module

    source_id, stream_id = _pair_camera_node_source(repository, node_id="node-old")
    monkeypatch.setattr(
        pr_module,
        "read_camera_node_transport_backlog_summary",
        lambda node_id, transport_root=None: (
            {"pending_count": 7, "pending_bytes": 12345, "failed_terminal_count": 0, "last_error": None, "reported_at": 0}
            if node_id == "node-old"
            else None
        ),
    )

    edit = repository.get_camera_configuration_edit(stream_id)
    preview = repository.preview_camera_configuration(
        stream_id,
        CameraConfigurationImpactPreviewRequest(
            provider_key="camera_node",
            expected_state_token=edit.state_token,
            config={"node_id": "node-new-hardware"},
            secret_actions={"node_id": CameraConfigurationSecretAction.replace},
            confirm_node_identity_change=True,
        ),
    )

    assert preview is not None
    assert preview.node_identity_replacement is not None
    assert preview.node_identity_replacement.pending_transport_backlog_count == 7
    assert "7 item(s)" in preview.node_identity_replacement.message


def test_old_node_transport_credential_stops_resolving_after_a_config_overwrite(repository) -> None:
    """Camera Node replacement's full preview/apply orchestration (see
    tests/test_camera_node_reprovision.py) always overwrites `config_json`
    wholesale with the new hardware's own freshly-minted credentials --
    this narrower test proves the specific, previously-untested downstream
    property agent archaeology flagged as "correct only incidentally": once
    that overwrite happens by any means, the *old* node's transport
    credential must no longer resolve to anything, including for a
    Node that goes on to attempt reconnecting after being replaced."""

    source_id, _stream_id = _pair_camera_node_source(
        repository, node_id="node-old-hardware", transport_credential="old-transport-credential"
    )
    assert repository.resolve_camera_node_transport_source("old-transport-credential") == (
        source_id,
        "node-old-hardware",
    )

    # The moment of replacement: config_json is overwritten wholesale with
    # the new physical Node's own identity/credentials (mirrors
    # `apply_camera_configuration`'s replacement branch, which does exactly
    # this -- `model.config_json = json.dumps(proposed_config, ...)`).
    repository.update_source_provider_configuration(
        source_id,
        SourceProviderConfigurationUpdate(
            provider_key="camera_node",
            config={
                "node_base_address": "http://192.168.1.51:8787",
                "node_credential": "new-pairing-credential-value",
                "node_transport_credential": "new-transport-credential",
                "node_camera_id": "cam-1",
                "node_id": "node-new-hardware",
                "node_pairing_state": "paired",
            },
        ),
    )

    # The old Node, unaware it was replaced, tries to reconnect and present
    # its own (still node-local, still plaintext-held) transport credential.
    assert repository.resolve_camera_node_transport_source("old-transport-credential") is None
    # The new Node's credential works, correctly and exclusively.
    assert repository.resolve_camera_node_transport_source("new-transport-credential") == (
        source_id,
        "node-new-hardware",
    )
