"""Research Export & Ecological Workflow Completion v1: `include_media` bytes
(see docs/research-export-ecological-workflow-completion-v1-contract.md).

Isolated `tmp_path` database, real candidate-Visit admission, reusing the
research-export repository fixtures so eligibility behavior is the same
boundary the rest of the export suite already proves.
"""

from __future__ import annotations

import csv
import hashlib
import os
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from mockingbird.api.schemas import (
    CamtrapDpExportRequest,
    ResearchExportFilters,
    ResearchExportRequest,
    ZoneType,
    ZoneUpdate,
)
from mockingbird.repository.product_repository import MediaAssetModel, ProductRepository
from mockingbird.research import media_bundle as media_bundle_module
from mockingbird.research.media_bundle import (
    MediaBundleRequest,
    plan_bundle_names,
)
from tests.conftest import de_demo_seeded_source
from tests.test_research_export_repository import (
    FEEDER_ZONE_ID,
    JPEG_BYTES,
    NOW,
    _activate,
    _create_visit,
    _review,
)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        research_export_root=tmp_path / "research_exports",
    )
    de_demo_seeded_source(repo)
    yield repo
    repo.close()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _reviewed_visit(repository: ProductRepository) -> str:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    return visit_id


def _visit_assets(repository: ProductRepository, visit_id: str) -> list[MediaAssetModel]:
    observations, _ = repository.research_export_eligibility_preview(
        ResearchExportFilters(visit_ids=[visit_id])
    )
    ids = {item.media_id for obs in observations for item in obs.evidence}
    assert ids
    with repository.session_factory() as session:
        return list(session.scalars(select(MediaAssetModel).where(MediaAssetModel.id.in_(ids))))


# --- inclusion on / off, checksum + manifest linkage -------------------------


def test_media_excluded_by_default_keeps_metadata_only_shape(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]))
    )
    output = Path(response.output_directory)
    assert not (output / "media").exists()
    assert not (output / "media-bundle.csv").exists()
    assert response.media_bundle is None and response.manifest.media_bundle is None
    assert "media-bundle.csv" not in {item.name for item in response.files}


def test_include_media_bundles_eligible_bytes_with_checksum_linkage(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    output = Path(response.output_directory)
    rows = _read_rows(output / "media-bundle.csv")
    assert rows and all(row["status"] == "bundled" for row in rows)
    for row in rows:
        bundled = output / row["bundled_path"]
        assert bundled.is_file() and not bundled.is_symlink()
        assert row["bundled_path"].startswith("media/")
        data = bundled.read_bytes()
        assert data == JPEG_BYTES
        assert hashlib.sha256(data).hexdigest() == row["sha256"]
        assert int(row["size_bytes"]) == len(data)
        assert visit_id in row["observation_ids"].split("|")
    summary = response.media_bundle
    assert summary.bundled == len(rows) and summary.omitted == 0 and summary.warnings == []
    assert summary.total_bytes == len(JPEG_BYTES) * len(rows)
    assert response.manifest.media_bundle == summary
    assert "media-bundle.csv" in {item.name for item in response.files}
    # manifest.json on disk carries the same summary the response did.
    assert '"bundled": %d' % len(rows) in (output / "manifest.json").read_text(encoding="utf-8")


def test_no_host_path_leaks_into_any_bundle_file(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    output = Path(response.output_directory)
    for path in output.rglob("*"):
        if path.is_file() and path.suffix in {".csv", ".json", ".jsonl"}:
            text = path.read_text(encoding="utf-8")
            assert str(repository.media_root) not in text
            assert str(output) not in text


def test_bundle_is_deterministic_across_exports(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    request = ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    first = Path(repository.export_research_dataset(request).output_directory)
    second = Path(repository.export_research_dataset(request).output_directory)
    assert (first / "media-bundle.csv").read_bytes() == (second / "media-bundle.csv").read_bytes()
    first_media = sorted(p.name for p in (first / "media").iterdir())
    assert first_media == sorted(p.name for p in (second / "media").iterdir())


def test_dry_run_with_media_reports_plan_and_copies_nothing(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    response = repository.export_research_dataset(
        ResearchExportRequest(
            filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True, dry_run=True,
        )
    )
    assert response.dry_run and response.output_directory is None
    assert response.media_bundle is not None and response.media_bundle.bundled >= 1
    assert not repository.research_export_root.exists() or not any(repository.research_export_root.iterdir())


# --- missing / unsafe / integrity --------------------------------------------


def test_missing_media_is_partial_success_with_explicit_warning(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    for asset in _visit_assets(repository, visit_id):
        Path(asset.local_path).unlink()
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    assert response.observation_count == 1  # truth export still succeeds
    summary = response.media_bundle
    assert summary.bundled == 0 and summary.omitted_reasons == {"omitted_missing": summary.omitted}
    assert summary.warnings and "omitted_missing" in summary.warnings[0]
    rows = _read_rows(Path(response.output_directory) / "media-bundle.csv")
    assert {row["status"] for row in rows} == {"omitted_missing"}
    assert all(row["bundled_path"] == "" and row["sha256"] == "" for row in rows)


def test_out_of_root_media_path_is_never_copied(repository: ProductRepository, tmp_path: Path) -> None:
    visit_id = _reviewed_visit(repository)
    secret = tmp_path / "outside-secret.jpg"
    secret.write_bytes(b"TOP-SECRET-HOST-FILE")
    with repository.session_factory() as session:
        for asset in _visit_assets(repository, visit_id):
            session.get(MediaAssetModel, asset.id).local_path = str(secret)
        session.commit()
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    assert response.media_bundle.omitted_reasons == {"omitted_unsafe_path": response.media_bundle.omitted}
    output = Path(response.output_directory)
    assert not any(b"TOP-SECRET-HOST-FILE" in p.read_bytes() for p in output.rglob("*") if p.is_file())
    assert str(secret) not in (output / "media-bundle.csv").read_text(encoding="utf-8")


def test_symlinked_media_is_never_followed(repository: ProductRepository, tmp_path: Path) -> None:
    visit_id = _reviewed_visit(repository)
    secret = tmp_path / "linked-secret.jpg"
    secret.write_bytes(b"X" * len(JPEG_BYTES))
    for asset in _visit_assets(repository, visit_id):
        path = Path(asset.local_path)
        path.unlink()
        try:
            os.symlink(secret, path)
        except OSError:
            pytest.skip("symlinks unavailable")
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    assert response.media_bundle.bundled == 0
    assert "omitted_unsafe_path" in response.media_bundle.omitted_reasons
    assert not list((Path(response.output_directory) / "media").iterdir())


def test_recorded_checksum_mismatch_omits_the_file(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    with repository.session_factory() as session:
        for asset in _visit_assets(repository, visit_id):
            session.get(MediaAssetModel, asset.id).content_sha256 = "0" * 64
        session.commit()
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    assert response.media_bundle.bundled == 0
    assert "omitted_integrity_mismatch" in response.media_bundle.omitted_reasons
    assert not list((Path(response.output_directory) / "media").iterdir())


# --- naming: traversal, collisions, duplicate references ----------------------


@pytest.mark.parametrize(
    "media_id",
    ["../../etc/passwd", "..", ".hidden", "a/b", "a\\b", "", "x" * 200, "/abs", "name\x00nul"],
)
def test_unsafe_media_ids_never_get_a_bundle_path(media_id: str) -> None:
    plan = plan_bundle_names([MediaBundleRequest(media_id, "image/jpeg", ("v1",))])
    assert plan[media_id].relative_path is None
    assert plan[media_id].omit_status == "omitted_unsafe_name"


def test_unsupported_content_type_is_not_bundled() -> None:
    plan = plan_bundle_names([MediaBundleRequest("m1", "application/x-sh", ("v1",))])
    assert plan["m1"].omit_status == "omitted_unsupported_type"


def test_case_insensitive_name_collision_omits_the_later_id() -> None:
    plan = plan_bundle_names(
        [
            MediaBundleRequest("Frame1", "image/jpeg", ("v1",)),
            MediaBundleRequest("frame1", "image/jpeg", ("v2",)),
        ]
    )
    assert plan["Frame1"].relative_path == "media/Frame1.jpg"
    assert plan["frame1"].relative_path is None
    assert plan["frame1"].omit_status == "omitted_name_collision"


def test_one_asset_referenced_by_two_observations_is_bundled_once() -> None:
    from mockingbird.research.media_bundle import media_requests_for_observations

    class _Item:
        def __init__(self, media_id: str) -> None:
            self.media_id, self.content_type = media_id, "image/jpeg"

    class _Obs:
        def __init__(self, observation_id: str) -> None:
            self.observation_id = observation_id
            self.evidence = (_Item("shared-frame"),)

    requests = media_requests_for_observations([_Obs("v2"), _Obs("v1")])
    assert len(requests) == 1
    assert requests[0].observation_ids == ("v1", "v2")


# --- eligibility: reviewed vs provisional, privacy, change in flight ----------


def test_provisional_visit_is_never_bundled_even_when_scoped_by_visit_id(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)  # never reviewed
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    assert response.observation_count == 0 and response.excluded_count == 1
    assert response.media_bundle.requested == 0
    assert not list((Path(response.output_directory) / "media").iterdir())


def test_privacy_zone_withheld_visit_contributes_no_media(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    repository.update_zone(FEEDER_ZONE_ID, ZoneUpdate(zone_type=ZoneType.privacy))
    response = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    assert response.observation_count == 0
    assert response.media_bundle.requested == 0


def test_eligibility_change_during_bundling_aborts_without_publishing(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    visit_id = _reviewed_visit(repository)
    original = repository._write_research_media_bundle

    def flip_after_copy(directory, planned):
        result = original(directory, planned)
        repository.update_zone(FEEDER_ZONE_ID, ZoneUpdate(zone_type=ZoneType.privacy))
        return result

    monkeypatch.setattr(repository, "_write_research_media_bundle", flip_after_copy)
    with pytest.raises(ValueError, match="research_export_eligibility_changed"):
        repository.export_research_dataset(
            ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
        )
    root = repository.research_export_root
    assert not root.exists() or not any(root.iterdir())


# --- bounds -------------------------------------------------------------------


def test_media_limit_refuses_export_and_dry_run(repository: ProductRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    visit_id = _reviewed_visit(repository)
    import mockingbird.repository.product_repository as repo_module

    monkeypatch.setattr(repo_module, "RESEARCH_EXPORT_MEDIA_MAX_FILES", 0)
    for dry_run in (True, False):
        with pytest.raises(ValueError, match="research_export_media_limit_exceeded"):
            repository.export_research_dataset(
                ResearchExportRequest(
                    filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True, dry_run=dry_run,
                )
            )
    monkeypatch.setattr(repo_module, "RESEARCH_EXPORT_MEDIA_MAX_FILES", 2000)
    monkeypatch.setattr(repo_module, "RESEARCH_EXPORT_MEDIA_MAX_TOTAL_BYTES", 1)
    with pytest.raises(ValueError, match="research_export_media_limit_exceeded"):
        repository.export_research_dataset(
            ResearchExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
        )
    root = repository.research_export_root
    assert not root.exists() or not any(root.iterdir())
    assert media_bundle_module.RESEARCH_EXPORT_MEDIA_MAX_FILES == 2000


# --- Camtrap DP -----------------------------------------------------------------


def test_camtrap_dp_include_media_writes_files_at_the_declared_file_path(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    response = repository.export_camtrap_dp_package(
        CamtrapDpExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    output = Path(response.output_directory)
    media_rows = _read_rows(output / "media.csv")
    assert media_rows
    for row in media_rows:
        assert (output / row["filePath"]).read_bytes() == JPEG_BYTES
    assert response.media_bundle.bundled == len(media_rows)
    assert response.validation.valid is True


def test_camtrap_dp_missing_media_is_a_disclosed_warning(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    for asset in _visit_assets(repository, visit_id):
        Path(asset.local_path).unlink()
    response = repository.export_camtrap_dp_package(
        CamtrapDpExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    assert response.media_bundle.bundled == 0
    assert any("omitted_missing" in warning for warning in response.validation.warnings)


def _assert_camtrap_never_advertises_missing_members(output: Path) -> list[dict[str, str]]:
    media_rows = _read_rows(output / "media.csv")
    for row in media_rows:
        assert (output / row["filePath"]).is_file(), f"advertises nonexistent member {row['filePath']}"
    advertised = {row["mediaID"] for row in media_rows}
    for row in _read_rows(output / "observations.csv"):
        assert row["mediaID"] == "" or row["mediaID"] in advertised
    return media_rows


def test_camtrap_dp_partial_success_never_advertises_a_nonexistent_member(repository: ProductRepository) -> None:
    first = _reviewed_visit(repository)
    second = _create_visit(
        repository, proposal_id="visit-episode:fixture-2", observed_at=NOW + timedelta(hours=2),
        captured_at=NOW + timedelta(hours=2),
    )
    _review(repository, second, "northern_cardinal")
    filters = ResearchExportFilters(visit_ids=[first, second])
    observations, _ = repository.research_export_eligibility_preview(filters)
    assert sum(1 for o in observations if o.eligibility.eligible) == 2
    with repository.session_factory() as session:
        assets = list(session.scalars(select(MediaAssetModel).order_by(MediaAssetModel.id)))
    media_ids = sorted({i.media_id for o in observations for i in o.evidence})
    assert len(media_ids) == 2, "partial success needs one surviving and one omitted asset"
    by_id = {a.id: a for a in assets}
    Path(by_id[media_ids[0]].local_path).unlink()
    survivors = {media_ids[1]}
    response = repository.export_camtrap_dp_package(CamtrapDpExportRequest(filters=filters, include_media=True))
    output = Path(response.output_directory)
    media_rows = _assert_camtrap_never_advertises_missing_members(output)
    assert {row["mediaID"] for row in media_rows} == survivors
    assert response.media_count == 1 and response.observation_count == 2
    assert response.validation.valid is True
    # Supplemental diagnostics still name the omitted file.
    statuses = {row["media_id"]: row["status"] for row in _read_rows(output / "media-bundle.csv")}
    assert statuses[media_ids[0]] == "omitted_missing" and statuses[media_ids[1]] == "bundled"
    assert any("omitted_missing" in w for w in response.validation.warnings)


@pytest.mark.parametrize("failure", ["missing", "checksum"])
def test_camtrap_dp_all_media_omitted_leaves_no_media_rows(repository: ProductRepository, failure: str) -> None:
    visit_id = _reviewed_visit(repository)
    for asset in _visit_assets(repository, visit_id):
        if failure == "missing":
            Path(asset.local_path).unlink()
        else:
            with repository.session_factory() as session, session.begin():
                session.get(MediaAssetModel, asset.id).content_sha256 = "0" * 64
    response = repository.export_camtrap_dp_package(
        CamtrapDpExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    output = Path(response.output_directory)
    assert _assert_camtrap_never_advertises_missing_members(output) == []
    assert response.media_count == 0 and response.observation_count >= 1
    assert response.validation.valid is True


def test_camtrap_dp_metadata_only_keeps_intended_file_paths(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    response = repository.export_camtrap_dp_package(
        CamtrapDpExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=False)
    )
    rows = _read_rows(Path(response.output_directory) / "media.csv")
    assert rows and all(row["filePath"].startswith("media/") for row in rows)


def test_generated_export_is_retrievable_as_a_zip_with_its_media(repository: ProductRepository) -> None:
    import zipfile

    from mockingbird.research.export_archive import build_export_archive

    visit_id = _reviewed_visit(repository)
    response = repository.export_camtrap_dp_package(
        CamtrapDpExportRequest(filters=ResearchExportFilters(visit_ids=[visit_id]), include_media=True)
    )
    archive_path, file_name = build_export_archive(repository.research_export_root, response.export_id)
    try:
        assert file_name == f"{response.export_id}.zip"
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            for row in _read_rows(Path(response.output_directory) / "media.csv"):
                assert archive.read(f"{response.export_id}/{row['filePath']}") == JPEG_BYTES
            assert f"{response.export_id}/datapackage.json" in names
            assert all(str(repository.research_export_root) not in n for n in names)
    finally:
        archive_path.unlink()


# --- visit_ids filter semantics ---------------------------------------------------


def test_visit_ids_filter_only_narrows(repository: ProductRepository) -> None:
    visit_id = _reviewed_visit(repository)
    all_obs, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    only, _ = repository.research_export_eligibility_preview(ResearchExportFilters(visit_ids=[visit_id]))
    assert [obs.observation_id for obs in only] == [visit_id]
    assert len(all_obs) >= len(only)
    none, _ = repository.research_export_eligibility_preview(ResearchExportFilters(visit_ids=["no-such-visit"]))
    assert none == []
