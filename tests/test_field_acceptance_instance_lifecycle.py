"""Structural tests for scripts/field_acceptance_instance_lifecycle.py.

See docs/field-acceptance-instance-lifecycle-storage-safety-v1-report.md
for the governing milestone. Entirely hermetic: no real `powershell.exe`
or Windows filesystem/process/network call anywhere in this file -- every
test drives the tool's orchestration against a small local fake
`WindowsHost`, mirroring (but not importing) `tests/test_deploy_windows_
dev.py`'s own established fake-host convention, scoped to only the
`WindowsHost` fields this tool actually calls (`local_appdata`, `http_get`,
`port_owner_pid`, `remove_tree`) -- every other field is a trivial,
never-exercised stub.

Fixture dev-roots are built directly on top of `deploy_windows_dev.py`'s
own real `append_deployment`/`write_current`/`ReleaseRecord`/
`CurrentPointer` functions (loaded the same `runpy.run_path` way the
module under test loads them), never a hand-rolled JSON shape of our own --
this is what makes "does this look like a real deploy-tool root"
meaningful to test at all.
"""

from __future__ import annotations

from pathlib import Path
import runpy
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_instance_lifecycle.py"))
_DWD = runpy.run_path(str(ROOT / "scripts" / "deploy_windows_dev.py"))

# --- names under test -------------------------------------------------------
InstanceLifecycleError = _MODULE["InstanceLifecycleError"]
InstanceManifest = _MODULE["InstanceManifest"]
MANIFEST_FILENAME = _MODULE["MANIFEST_FILENAME"]
PURPOSE_FIELD_ACCEPTANCE = _MODULE["PURPOSE_FIELD_ACCEPTANCE"]
LIFECYCLE_ACTIVE = _MODULE["LIFECYCLE_ACTIVE"]
LIFECYCLE_COMPLETED = _MODULE["LIFECYCLE_COMPLETED"]
LIFECYCLE_ARCHIVED = _MODULE["LIFECYCLE_ARCHIVED"]
SAFE_TO_RECLAIM = _MODULE["SAFE_TO_RECLAIM"]
NOT_RECLAIMABLE_ACTIVE = _MODULE["NOT_RECLAIMABLE_ACTIVE"]
NOT_RECLAIMABLE_UNARCHIVED = _MODULE["NOT_RECLAIMABLE_UNARCHIVED"]
NOT_RECLAIMABLE_UNKNOWN_INSTANCE = _MODULE["NOT_RECLAIMABLE_UNKNOWN_INSTANCE"]
ACCEPTANCE_RECORDER_HARD_CEILING_BYTES = _MODULE["ACCEPTANCE_RECORDER_HARD_CEILING_BYTES"]

read_manifest = _MODULE["read_manifest"]
write_manifest = _MODULE["write_manifest"]
init_instance = _MODULE["init_instance"]
assess_instance = _MODULE["assess_instance"]
complete_instance = _MODULE["complete_instance"]
mark_archived = _MODULE["mark_archived"]
verify_archive_contract = _MODULE["verify_archive_contract"]
plan_cleanup = _MODULE["plan_cleanup"]
execute_cleanup = _MODULE["execute_cleanup"]
storage_preflight_report = _MODULE["storage_preflight_report"]
scan_sibling_instances = _MODULE["scan_sibling_instances"]
directory_size_bytes = _MODULE["directory_size_bytes"]
refuse_unsafe_root = _MODULE["refuse_unsafe_root"]
main = _MODULE["main"]

WindowsHost = _DWD["WindowsHost"]
HttpProbe = _DWD["HttpProbe"]
ReleaseRecord = _DWD["ReleaseRecord"]
CurrentPointer = _DWD["CurrentPointer"]
append_deployment = _DWD["append_deployment"]
write_current = _DWD["write_current"]
DEV_ROOT_DIRNAME = _DWD["DEV_ROOT_DIRNAME"]
DEFAULT_PORT = _DWD["DEFAULT_PORT"]


# ---------------------------------------------------------------------------
# Fake WindowsHost: an in-memory fake port/process table plus plain temp-
# directory filesystem operations -- scoped to only what this tool calls.
# ---------------------------------------------------------------------------


class FakeOS:
    def __init__(self) -> None:
        self._next_pid = 1000
        self.listeners: dict[int, dict] = {}
        self.removed_paths: list[Path] = []

    def start_listener(self, *, port: int, git_commit: str, build_id: str, instance_id: str = "a" * 32, app_version: str = "0.1.0") -> int:
        pid = self._next_pid
        self._next_pid += 1
        self.listeners[port] = {
            "pid": pid, "git_commit": git_commit, "build_id": build_id,
            "instance_id": instance_id, "app_version": app_version,
        }
        return pid

    def stop_listener(self, port: int) -> None:
        self.listeners.pop(port, None)


def make_fake_windows_host(fake_os: FakeOS, *, local_appdata: Path) -> WindowsHost:
    def http_get(url: str, _timeout: float) -> HttpProbe:
        # url shape: http://host:port/health  or  http://host:port/api/product/instance
        try:
            _scheme, rest = url.split("://", 1)
            hostport, path = rest.split("/", 1)
            port = int(hostport.split(":")[1])
        except (ValueError, IndexError):
            return HttpProbe(ok=False, error="malformed url")
        entry = fake_os.listeners.get(port)
        if entry is None:
            return HttpProbe(ok=False, error="connection refused")
        if path == "health":
            return HttpProbe(ok=True, status=200, json_body={"status": "ok"})
        if path == "api/product/instance":
            return HttpProbe(
                ok=True, status=200,
                json_body={
                    "instance_id": entry["instance_id"], "git_commit": entry["git_commit"],
                    "build_id": entry["build_id"], "app_version": entry["app_version"],
                },
            )
        return HttpProbe(ok=False, status=404, error="not found")

    def port_owner_pid(port: int) -> int | None:
        entry = fake_os.listeners.get(port)
        return entry["pid"] if entry else None

    def remove_tree(path: Path) -> None:
        fake_os.removed_paths.append(Path(path))
        shutil.rmtree(path)

    return WindowsHost(
        local_appdata=lambda: local_appdata,
        to_windows_path=lambda path: str(path),
        ensure_dir=lambda path: Path(path).mkdir(parents=True, exist_ok=True),
        copy_file=lambda source, destination: shutil.copy2(source, destination),
        rename=lambda source, destination: Path(source).rename(destination),
        make_junction=lambda link, target: None,
        remove_junction=lambda link: None,
        remove_tree=remove_tree,
        launch_release=lambda release_dir, extra_env: None,
        http_get=http_get,
        port_owner_pid=port_owner_pid,
        process_alive=lambda pid: False,
        process_image_path=lambda pid: None,
        kill_process=lambda pid: None,
        run_bioclip_runtime_check=lambda release_dir, timeout: None,
    )


@pytest.fixture
def fake_os() -> FakeOS:
    return FakeOS()


@pytest.fixture
def fake_host(fake_os: FakeOS, tmp_path: Path) -> WindowsHost:
    return make_fake_windows_host(fake_os, local_appdata=tmp_path / "LOCALAPPDATA")


def _make_deploy_tool_root(
    root: Path, *, windows_host: WindowsHost, sha: str = "abc1234", git_commit: str = "a" * 40,
    build_id: str = "build-1", port: int = DEFAULT_PORT,
) -> None:
    """The smallest real, on-disk shape `deploy_windows_dev.py` itself
    would have produced: a `releases/deployments.json` ledger entry plus a
    `releases/current.json` pointer -- built via that file's own real
    `append_deployment`/`write_current`, never a hand-rolled JSON shape."""

    root.mkdir(parents=True, exist_ok=True)
    (root / "userdata").mkdir(parents=True, exist_ok=True)
    record = ReleaseRecord(
        sha=sha, full_commit=git_commit, build_id=build_id, app_version="0.1.0",
        runtime_hash="rt1", model_hash="md1", deployed_at="2026-09-02T00:00:00+00:00",
    )
    append_deployment(root, record, windows_host=windows_host)
    write_current(root, CurrentPointer(sha=sha, pid=None, port=port), windows_host=windows_host)


def _make_evidence_archive(root: Path) -> Path:
    archive = root / "evidence-archive"
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "PROVENANCE.md").write_text("# provenance\n", encoding="utf-8")
    (archive / "counterfactual-FINAL.json").write_text("{}", encoding="utf-8")
    return archive


# ---------------------------------------------------------------------------
# Identification
# ---------------------------------------------------------------------------


def test_init_marks_a_real_deploy_tool_root(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host, git_commit="c" * 40, build_id="build-x")

    manifest = init_instance(dev_root=root, windows_host=fake_host)

    assert manifest.purpose == PURPOSE_FIELD_ACCEPTANCE
    assert manifest.lifecycle_state == LIFECYCLE_ACTIVE
    assert manifest.dev_root == str(root.resolve())
    assert manifest.created_by_commit == "c" * 40
    assert manifest.created_by_build_id == "build-x"
    assert (root / MANIFEST_FILENAME).is_file()
    assert read_manifest(root) == manifest


def test_init_refuses_directory_with_no_deployments_ledger(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "SomeRandomFolder"
    root.mkdir()

    with pytest.raises(InstanceLifecycleError, match="deployments.json"):
        init_instance(dev_root=root, windows_host=fake_host)
    assert not (root / MANIFEST_FILENAME).exists()


def test_init_refuses_the_default_shared_dev_root(fake_os: FakeOS, tmp_path: Path) -> None:
    local_appdata = tmp_path / "LOCALAPPDATA"
    fake_host = make_fake_windows_host(fake_os, local_appdata=local_appdata)
    default_root = local_appdata / DEV_ROOT_DIRNAME
    _make_deploy_tool_root(default_root, windows_host=fake_host)

    with pytest.raises(InstanceLifecycleError, match="shared persistent dev root"):
        init_instance(dev_root=default_root, windows_host=fake_host)


def test_init_refuses_to_overwrite_an_existing_manifest_without_force(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    first = init_instance(dev_root=root, windows_host=fake_host)

    with pytest.raises(InstanceLifecycleError, match="already marked"):
        init_instance(dev_root=root, windows_host=fake_host)

    forced = init_instance(dev_root=root, windows_host=fake_host, force=True)
    assert forced.created_at == first.created_at  # preserves the original creation fact


def test_assess_rejects_an_ordinary_unmarked_deploy_tool_root(fake_host: WindowsHost, tmp_path: Path) -> None:
    """The operator's persistent MockingBirdDev (real releases, never
    `init`'d) must never be reclaimable through this path."""

    root = tmp_path / "MockingBirdDev"
    _make_deploy_tool_root(root, windows_host=fake_host)

    result = assess_instance(dev_root=root, windows_host=fake_host)

    assert result.verdict == NOT_RECLAIMABLE_UNKNOWN_INSTANCE
    assert result.identity_confirmed is False


def test_assess_rejects_a_completely_unknown_directory(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "not_even_a_deploy_root"
    root.mkdir()

    result = assess_instance(dev_root=root, windows_host=fake_host)

    assert result.verdict == NOT_RECLAIMABLE_UNKNOWN_INSTANCE


def test_assess_never_walks_the_filesystem_for_an_unrecognized_directory(
    fake_host: WindowsHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real-Windows-proof-discovered regression guard: a refusal must be
    immediate, never preceded by an expensive recursive byte-count walk --
    against a real, large, long-lived persistent dev-root (accessed
    through the slow WSL<->Windows filesystem bridge), the unconditional
    version of this call turned an instant refusal into a multi-minute
    hang. `directory_size_bytes` must not even be called on this path."""

    root = tmp_path / "MockingBirdDev"  # unmarked -- never init'd
    root.mkdir()
    monkeypatch.setitem(
        _MODULE, "directory_size_bytes",
        lambda _root: (_ for _ in ()).throw(AssertionError("must not walk an unrecognized directory")),
    )

    result = assess_instance(dev_root=root, windows_host=fake_host)

    assert result.verdict == NOT_RECLAIMABLE_UNKNOWN_INSTANCE
    assert result.size_on_disk_bytes is None


def test_assess_rejects_a_manifest_whose_identity_does_not_match_its_location(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """A manifest copied/relocated from elsewhere (or a symlink pretending
    to be a different root) must never be trusted just because a file with
    the right name exists here."""

    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    other_root = tmp_path / "SomewhereElseEntirely"
    mismatched = InstanceManifest(
        schema_version=1, purpose=PURPOSE_FIELD_ACCEPTANCE, dev_root=str(other_root),
        created_at="2026-01-01T00:00:00+00:00", created_by_commit=None, created_by_build_id=None,
        lifecycle_state=LIFECYCLE_ACTIVE,
    )
    write_manifest(root, mismatched)

    result = assess_instance(dev_root=root, windows_host=fake_host)

    assert result.verdict == NOT_RECLAIMABLE_UNKNOWN_INSTANCE


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_assess_running_instance_is_not_reclaimable(fake_os: FakeOS, fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host, git_commit="d" * 40, build_id="build-d")
    init_instance(dev_root=root, windows_host=fake_host)
    fake_os.start_listener(port=DEFAULT_PORT, git_commit="d" * 40, build_id="build-d")

    result = assess_instance(dev_root=root, windows_host=fake_host)

    assert result.verdict == NOT_RECLAIMABLE_ACTIVE
    assert result.process_running is True
    assert "stop it first" in result.reason


def test_complete_refuses_while_the_process_is_still_running(
    fake_os: FakeOS, fake_host: WindowsHost, tmp_path: Path,
) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host, git_commit="e" * 40, build_id="build-e")
    init_instance(dev_root=root, windows_host=fake_host)
    fake_os.start_listener(port=DEFAULT_PORT, git_commit="e" * 40, build_id="build-e")

    with pytest.raises(InstanceLifecycleError, match="still running"):
        complete_instance(dev_root=root, windows_host=fake_host)
    assert read_manifest(root).lifecycle_state == LIFECYCLE_ACTIVE


def test_complete_transitions_to_completed_once_verified_stopped(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    # never started -- nothing to stop, matching a real graceful `--stop`
    # having already succeeded.

    manifest = complete_instance(dev_root=root, windows_host=fake_host)

    assert manifest.lifecycle_state == LIFECYCLE_COMPLETED
    assert manifest.completed_at is not None


def test_assess_completed_but_unarchived_is_not_reclaimable(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    complete_instance(dev_root=root, windows_host=fake_host)

    result = assess_instance(dev_root=root, windows_host=fake_host)

    assert result.verdict == NOT_RECLAIMABLE_UNARCHIVED
    assert result.lifecycle_state == LIFECYCLE_COMPLETED
    assert "mark-archived" in result.reason


def test_interrupted_session_never_marked_complete_is_not_reclaimable(fake_host: WindowsHost, tmp_path: Path) -> None:
    """Governing brief §20: a crash must never be silently treated as
    archived -- it stays non-reclaimable until an operator deliberately
    resolves evidence disposition."""

    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    # The process crashed: nothing is listening, but nobody ever called
    # `complete` -- lifecycle_state is still "active".

    result = assess_instance(dev_root=root, windows_host=fake_host)

    assert result.verdict == NOT_RECLAIMABLE_UNARCHIVED
    assert result.lifecycle_state == LIFECYCLE_ACTIVE
    assert "crash or an interrupted session" in result.reason


def test_mark_archived_refuses_before_completed(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    archive = _make_evidence_archive(tmp_path)

    with pytest.raises(InstanceLifecycleError, match="not been marked 'completed'"):
        mark_archived(dev_root=root, evidence_archive=archive)


def test_mark_archived_refuses_an_incomplete_evidence_directory(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    complete_instance(dev_root=root, windows_host=fake_host)
    empty_archive = tmp_path / "empty-archive"
    empty_archive.mkdir()

    with pytest.raises(InstanceLifecycleError, match="missing"):
        mark_archived(dev_root=root, evidence_archive=empty_archive)
    assert read_manifest(root).lifecycle_state == LIFECYCLE_COMPLETED


def test_mark_archived_succeeds_and_assess_now_reports_safe_to_reclaim(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    complete_instance(dev_root=root, windows_host=fake_host)
    archive = _make_evidence_archive(tmp_path)

    manifest = mark_archived(dev_root=root, evidence_archive=archive)
    assert manifest.lifecycle_state == LIFECYCLE_ARCHIVED
    assert manifest.evidence_archive_path == str(archive.resolve())

    result = assess_instance(dev_root=root, windows_host=fake_host)
    assert result.verdict == SAFE_TO_RECLAIM
    assert result.reclaimable_bytes is not None and result.reclaimable_bytes > 0


def test_verify_archive_contract_categories() -> None:
    ok, missing = verify_archive_contract(Path("/does/not/exist"))
    assert ok is False
    assert set(missing) == {"written_report_or_provenance", "raw_evidence_or_accounting"}


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def _archived_root(root: Path, *, fake_host: WindowsHost, tmp_path: Path, tag: str = "") -> Path:
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    complete_instance(dev_root=root, windows_host=fake_host)
    archive = _make_evidence_archive(tmp_path / f"archive{tag}")
    mark_archived(dev_root=root, evidence_archive=archive)
    (root / "userdata" / "big-recorder-output.jpg").write_bytes(b"x" * 1024)
    return root


def test_cleanup_dry_run_lists_exact_target_without_deleting(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = _archived_root(tmp_path / "MockingBirdFieldAcceptanceX", fake_host=fake_host, tmp_path=tmp_path)

    plan = plan_cleanup(dev_root=root, windows_host=fake_host)

    assert plan.blocked is False
    assert "userdata" in plan.will_remove and "releases" in plan.will_remove
    assert plan.total_bytes is not None and plan.total_bytes > 0
    assert root.is_dir()  # nothing was removed

    # `cleanup` without --destroy must behave identically to the plan.
    result = execute_cleanup(dev_root=root, windows_host=fake_host, destroy=False)
    assert result.destroyed is False
    assert root.is_dir()


def test_cleanup_destroy_removes_only_the_approved_root(fake_host: WindowsHost, fake_os: FakeOS, tmp_path: Path) -> None:
    target = _archived_root(tmp_path / "MockingBirdFieldAcceptanceX", fake_host=fake_host, tmp_path=tmp_path, tag="-x")
    sibling = _archived_root(tmp_path / "MockingBirdFieldAcceptanceY", fake_host=fake_host, tmp_path=tmp_path, tag="-y")
    unrelated = tmp_path / "unrelated-directory"
    unrelated.mkdir()
    (unrelated / "keep-me.txt").write_text("do not touch", encoding="utf-8")

    result = execute_cleanup(dev_root=target, windows_host=fake_host, destroy=True)

    assert result.destroyed is True
    assert not target.exists()
    assert sibling.exists() and (sibling / "userdata").exists()
    assert (unrelated / "keep-me.txt").is_file()


def test_cleanup_refuses_an_unmarked_wrong_target(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdDev"
    _make_deploy_tool_root(root, windows_host=fake_host)  # never init'd

    result = execute_cleanup(dev_root=root, windows_host=fake_host, destroy=True)

    assert result.blocked is True
    assert result.destroyed is False
    assert root.exists()


def test_cleanup_refuses_a_running_instance(fake_os: FakeOS, fake_host: WindowsHost, tmp_path: Path) -> None:
    root = _archived_root(tmp_path / "MockingBirdFieldAcceptanceX", fake_host=fake_host, tmp_path=tmp_path)
    manifest = read_manifest(root)
    # Simulate the process having been relaunched again after archiving --
    # the stored manifest still says "archived", but a fresh re-check must
    # still refuse (governing brief §7's own "never trust a stale
    # recorded fact alone" invariant).
    current = _DWD["read_current"](root)
    fake_os.start_listener(port=current.port, git_commit=manifest.created_by_commit or "z" * 40, build_id=manifest.created_by_build_id or "build-z")

    result = execute_cleanup(dev_root=root, windows_host=fake_host, destroy=True)

    assert result.blocked is True
    assert root.exists()


def test_cleanup_double_destroy_is_idempotent_and_safe(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = _archived_root(tmp_path / "MockingBirdFieldAcceptanceX", fake_host=fake_host, tmp_path=tmp_path)

    first = execute_cleanup(dev_root=root, windows_host=fake_host, destroy=True)
    assert first.destroyed is True
    assert not root.exists()

    second = execute_cleanup(dev_root=root, windows_host=fake_host, destroy=True)
    assert second.destroyed is False
    assert second.blocked is True  # now NOT_RECLAIMABLE_UNKNOWN_INSTANCE -- no crash, no error


def test_cleanup_refuses_a_top_level_symlink_escaping_the_root(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = _archived_root(tmp_path / "MockingBirdFieldAcceptanceX", fake_host=fake_host, tmp_path=tmp_path)
    outside = tmp_path / "outside-target"
    outside.mkdir()
    (outside / "do-not-delete.txt").write_text("precious", encoding="utf-8")
    (root / "escape-link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(InstanceLifecycleError, match="outside itself"):
        execute_cleanup(dev_root=root, windows_host=fake_host, destroy=True)
    assert (outside / "do-not-delete.txt").is_file()
    assert root.exists()


def test_cleanup_refuses_filesystem_root_and_home_directory(fake_host: WindowsHost) -> None:
    with pytest.raises(InstanceLifecycleError, match="filesystem root"):
        refuse_unsafe_root(Path("/"), windows_host=fake_host, dwd=_DWD)

    import os

    home = Path(os.path.expanduser("~")).resolve()
    with pytest.raises(InstanceLifecycleError, match="home directory"):
        refuse_unsafe_root(home, windows_host=fake_host, dwd=_DWD)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class _FakeUsage:
    def __init__(self, *, total: int, free: int) -> None:
        self.total = total
        self.free = free
        self.used = total - free


def test_storage_preflight_sufficient_headroom_passes(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceNew"
    root.mkdir()

    report = storage_preflight_report(
        dev_root=root, windows_host=fake_host, recorder_max_bytes=1_000_000_000,
        disk_usage_fn=lambda _path: _FakeUsage(total=100_000_000_000, free=50_000_000_000),
        scan_siblings=False,
    )

    assert report.sufficient is True
    assert "OK to proceed" in report.reason


def test_storage_preflight_insufficient_headroom_fails_before_expensive_session(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceNew"
    root.mkdir()

    report = storage_preflight_report(
        dev_root=root, windows_host=fake_host, recorder_max_bytes=4_000_000_000,
        disk_usage_fn=lambda _path: _FakeUsage(total=100_000_000_000, free=1_370_000_000),  # v9's real ~1.37GB
        scan_siblings=False,
    )

    assert report.sufficient is False
    assert "Insufficient storage" in report.reason
    assert "1.4GB free" in report.reason or "1.37GB free" in report.reason or "GB free" in report.reason


def test_storage_preflight_rejects_recorder_budget_over_hard_ceiling(fake_host: WindowsHost, tmp_path: Path) -> None:
    root = tmp_path / "whatever"
    with pytest.raises(InstanceLifecycleError, match="hard ceiling"):
        storage_preflight_report(
            dev_root=root, windows_host=fake_host,
            recorder_max_bytes=ACCEPTANCE_RECORDER_HARD_CEILING_BYTES + 1,
            disk_usage_fn=lambda _path: _FakeUsage(total=1, free=1), scan_siblings=False,
        )


def test_storage_preflight_reports_known_reclaimable_bytes_from_sibling_instance(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    parent = tmp_path / "LOCALAPPDATA"  # matches fake_host's own local_appdata() exactly
    reclaimable = _archived_root(parent / "MockingBirdFieldAcceptanceOld", fake_host=fake_host, tmp_path=tmp_path)
    new_root = parent / "MockingBirdFieldAcceptanceNew"
    new_root.mkdir()

    report = storage_preflight_report(
        dev_root=new_root, windows_host=fake_host, recorder_max_bytes=1_000_000_000,
        disk_usage_fn=lambda _path: _FakeUsage(total=100_000_000_000, free=2_000_000_000),
        scan_siblings=True,
    )

    assert str(reclaimable.resolve()) in report.known_reclaimable_instances
    assert report.known_reclaimable_bytes > 0


# ---------------------------------------------------------------------------
# Storage-preflight cross-OS path correctness -- Field Acceptance Evidence
# Integrity & Storage Preflight Correctness v1. `storage_preflight_report`
# delegates target resolution to `deploy_windows_dev.
# resolve_storage_probe_target` (loaded via `_dwd()`) -- see that
# function's own tests in tests/test_deploy_windows_dev.py for the
# resolver's own unit coverage; these tests confirm the *delegation*
# itself (provenance fields threaded through, DeploymentError re-raised
# as this module's own InstanceLifecycleError) at the tool a real field
# session actually runs (`preflight`).
# ---------------------------------------------------------------------------


def test_storage_preflight_reports_provenance_for_an_ordinary_target(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceNew"
    root.mkdir()

    report = storage_preflight_report(
        dev_root=root, windows_host=fake_host, recorder_max_bytes=1_000_000_000,
        disk_usage_fn=lambda _path: _FakeUsage(total=100_000_000_000, free=50_000_000_000),
        scan_siblings=False, is_native_windows=False,
    )

    assert report.requested_root == str(root)
    assert report.resolved_root == str(root.resolve())
    assert report.probed_root == str(root.resolve())
    assert report.resolution_method == "direct"
    assert report.platform == "posix"
    assert report.filesystem_device_id is not None  # cheaply available via os.stat -- a real device id


def test_storage_preflight_windows_drive_path_on_posix_fails_closed_without_translation(
    fake_host: WindowsHost,
) -> None:
    """The exact Representative Daylight Gate A Field Acceptance v12
    defect, reproduced at the operator-facing `preflight` command itself:
    a malformed Windows-style `--dev-root` under POSIX, with no
    trustworthy `wslpath` translation available. Must raise this module's
    own `InstanceLifecycleError` (never a raw `DeploymentError` leaking
    from `deploy_windows_dev.py`, and never a silent wrong-filesystem
    'success') -- and must never call `disk_usage_fn` at all."""

    def _disk_usage_must_not_be_called(_path: str) -> None:
        raise AssertionError("disk_usage_fn must never be called once resolution has failed closed")

    with pytest.raises(InstanceLifecycleError, match="wslpath"):
        storage_preflight_report(
            dev_root=Path(r"C:\Users\exampleuser\AppData\Local\MockingBirdFieldAcceptanceV12"),
            windows_host=fake_host, recorder_max_bytes=1_000_000_000,
            disk_usage_fn=_disk_usage_must_not_be_called,
            scan_siblings=False, is_native_windows=False, wsl_translate_fn=lambda _raw: None,
        )


def test_storage_preflight_windows_drive_path_translates_and_reports_provenance(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """The correct, supported form: once translated, the report's own
    provenance fields let a reviewer see exactly what was requested versus
    what was actually measured -- 'requested Windows instance root ->
    measured Windows storage', never the v12 case, 'requested Windows root
    -> measured WSL virtual disk' (governing brief §14)."""

    windows_style = r"C:\Users\exampleuser\AppData\Local\MockingBirdFieldAcceptanceV12"
    fake_mount_root = tmp_path / "mnt-sim" / "c-sim"
    fake_mount_root.mkdir(parents=True)
    translated = str(fake_mount_root / "Users" / "exampleuser" / "AppData" / "Local" / "MockingBirdFieldAcceptanceV12")

    report = storage_preflight_report(
        dev_root=Path(windows_style), windows_host=fake_host, recorder_max_bytes=1_000_000_000,
        disk_usage_fn=lambda _path: _FakeUsage(total=100_000_000_000, free=50_000_000_000),
        scan_siblings=False, is_native_windows=False, wsl_translate_fn=lambda _raw: translated,
    )

    assert report.requested_root == windows_style
    assert report.resolved_root == translated
    assert report.probed_root == str(fake_mount_root)  # nearest existing ancestor -- target itself is fresh
    assert report.resolution_method == "translated_from_windows_drive_path"
    assert report.sufficient is True
    assert str(ROOT) not in report.probed_root  # never the repo checkout / CWD


def test_storage_preflight_nested_nonexistent_target_resolves_to_correct_ancestor(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """Governing brief §15: a fresh target nested several levels below
    the nearest real directory (not just one level) still resolves
    correctly -- see the identical resolver-level test in
    tests/test_deploy_windows_dev.py for the underlying mechanism; this
    confirms it end to end through `storage_preflight_report` itself."""

    existing = tmp_path / "mnt-sim" / "c-sim" / "MockingBird"
    existing.mkdir(parents=True)
    deeply_nested = existing / "NewInstance" / "Deep" / "Nested"

    report = storage_preflight_report(
        dev_root=deeply_nested, windows_host=fake_host, recorder_max_bytes=1_000_000_000,
        disk_usage_fn=lambda _path: _FakeUsage(total=100_000_000_000, free=50_000_000_000),
        scan_siblings=False, is_native_windows=False,
    )

    assert report.probed_root == str(existing)


# ---------------------------------------------------------------------------
# Field Acceptance Tooling Correctness & Preflight Closure v1: dev-root
# path-resolution consistency across every subcommand, not just `preflight`.
# Representative Daylight True-Latency Tail Convergence v3's own Defect #2:
# `init` rejected the identical Windows-style `--dev-root` string
# `preflight` had, minutes earlier, correctly translated
# (`"resolution_method": "translated_from_windows_drive_path"`) -- producing
# a garbled error concatenating the WSL cwd with the raw backslash string.
# `init_instance`/`assess_instance`/`complete_instance`/`mark_archived`/
# `plan_cleanup`/`execute_cleanup` now all resolve `--dev-root` through the
# exact same `_resolve_dev_root` -> `deploy_windows_dev.resolve_dev_root_
# path` boundary `preflight` already used -- these tests confirm the fix at
# the same tools a real field session actually runs.
# ---------------------------------------------------------------------------


def test_init_accepts_a_windows_style_dev_root_matching_preflights_own_translation(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """The exact Representative Daylight True-Latency Tail Convergence v3
    workaround, closed: `init` now accepts the identical Windows-style
    string `preflight` already accepted, and resolves to the identical
    real target -- never a second, silently-diverging translation."""

    windows_style = r"C:\Users\exampleuser\AppData\Local\MockingBirdLatencyConvergenceV3"
    fake_mount_root = tmp_path / "mnt-sim" / "c-sim"
    translated = fake_mount_root / "Users" / "exampleuser" / "AppData" / "Local" / "MockingBirdLatencyConvergenceV3"
    _make_deploy_tool_root(translated, windows_host=fake_host, git_commit="d" * 40, build_id="build-v3")

    manifest = init_instance(
        dev_root=Path(windows_style), windows_host=fake_host,
        is_native_windows=False, wsl_translate_fn=lambda _raw: str(translated),
    )

    assert manifest.dev_root == str(translated.resolve())
    assert manifest.created_by_commit == "d" * 40
    assert (translated / MANIFEST_FILENAME).is_file()
    assert str(ROOT) not in manifest.dev_root  # never the repo checkout / CWD -- the pre-fix garbled shape


def test_init_fails_closed_for_a_windows_style_dev_root_with_no_translation_available(
    fake_host: WindowsHost,
) -> None:
    """Never silently CWD-anchors a Windows-style path into relative
    garbage (the exact pre-fix defect) -- fails closed with the same
    clear, actionable `InstanceLifecycleError` `preflight` already gives
    for this identical situation, never a bare traceback and never a
    fabricated manifest somewhere unexpected."""

    with pytest.raises(InstanceLifecycleError, match="wslpath"):
        init_instance(
            dev_root=Path(r"C:\Users\exampleuser\AppData\Local\MockingBirdMissingTranslation"),
            windows_host=fake_host, is_native_windows=False, wsl_translate_fn=lambda _raw: None,
        )


def test_init_handles_a_windows_style_dev_root_containing_spaces(fake_host: WindowsHost, tmp_path: Path) -> None:
    """Governing brief §3: 'valid paths with spaces handled safely.'
    Spaces are ordinary characters to `wslpath` (invoked via an argv list,
    never a shell string) -- this proves the whole path survives end to
    end, manifest included, not merely that translation itself does not
    crash."""

    windows_style = r"C:\Users\zach k\AppData\Local\Field Acceptance V3"
    fake_mount_root = tmp_path / "mnt-sim" / "c-sim"
    translated = fake_mount_root / "Users" / "zach k" / "AppData" / "Local" / "Field Acceptance V3"
    _make_deploy_tool_root(translated, windows_host=fake_host)

    manifest = init_instance(
        dev_root=Path(windows_style), windows_host=fake_host,
        is_native_windows=False, wsl_translate_fn=lambda _raw: str(translated),
    )

    assert manifest.dev_root == str(translated.resolve())
    assert (translated / MANIFEST_FILENAME).is_file()


def test_init_is_idempotent_across_two_spellings_of_the_same_real_directory(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """Governing brief §3: 'idempotent initialization.' A Windows-style
    spelling and the equivalent already-WSL-visible spelling of the *same*
    real directory must resolve to the identical manifest location -- the
    second `init` (without --force) correctly recognizes 'already marked'
    rather than silently creating a second, divergent manifest reachable
    only through the other spelling."""

    real_root = tmp_path / "MockingBirdFieldAcceptanceIdempotent"
    _make_deploy_tool_root(real_root, windows_host=fake_host)

    first = init_instance(dev_root=real_root, windows_host=fake_host)  # ordinary WSL-visible spelling
    with pytest.raises(InstanceLifecycleError, match="already marked"):
        init_instance(
            dev_root=Path(r"C:\Users\exampleuser\AppData\Local\MockingBirdFieldAcceptanceIdempotent"),
            windows_host=fake_host, is_native_windows=False, wsl_translate_fn=lambda _raw: str(real_root),
        )
    assert read_manifest(real_root).created_at == first.created_at


def test_assess_complete_and_cleanup_also_accept_a_windows_style_dev_root(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """The fix is tool-wide, not scoped to `init` alone -- every lifecycle
    transition a real field session runs end to end accepts the identical
    Windows-style spelling, closing 'one documented, canonical input-path
    convention' for the whole tool."""

    fake_mount_root = tmp_path / "mnt-sim" / "c-sim"
    translated = fake_mount_root / "Users" / "exampleuser" / "AppData" / "Local" / "MockingBirdWideCheck"
    windows_style = Path(r"C:\Users\exampleuser\AppData\Local\MockingBirdWideCheck")
    translate = lambda _raw: str(translated)  # noqa: E731
    _make_deploy_tool_root(translated, windows_host=fake_host)

    init_instance(dev_root=windows_style, windows_host=fake_host, is_native_windows=False, wsl_translate_fn=translate)
    assessed = assess_instance(
        dev_root=windows_style, windows_host=fake_host, is_native_windows=False, wsl_translate_fn=translate,
    )
    assert assessed.identity_confirmed is True

    completed = complete_instance(
        dev_root=windows_style, windows_host=fake_host, is_native_windows=False, wsl_translate_fn=translate,
    )
    assert completed.lifecycle_state == LIFECYCLE_COMPLETED

    archive = _make_evidence_archive(tmp_path)
    archived = mark_archived(
        dev_root=windows_style, evidence_archive=archive, is_native_windows=False, wsl_translate_fn=translate,
    )
    assert archived.lifecycle_state == LIFECYCLE_ARCHIVED

    plan = execute_cleanup(
        dev_root=windows_style, windows_host=fake_host, destroy=True,
        is_native_windows=False, wsl_translate_fn=translate,
    )
    assert plan.destroyed is True
    assert not translated.exists()


# ---------------------------------------------------------------------------
# Cache separation / shared-cache safety
# ---------------------------------------------------------------------------


def test_cleanup_never_touches_a_sibling_instances_cache_or_userdata(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """Each dev-root's runtime/model/BioCLIP cache tiers are private to it
    (never shared across separate --dev-root instances -- see the module
    docstring's "Cache scope" and the v8 field report's own direct
    confirmation of this). Destroying one disposable instance must never
    reach into another's cache."""

    target = _archived_root(tmp_path / "MockingBirdFieldAcceptanceX", fake_host=fake_host, tmp_path=tmp_path, tag="-x")
    (target / "runtime" / "somehash").mkdir(parents=True)
    (target / "runtime" / "somehash" / "big.dll").write_bytes(b"x" * 4096)
    sibling = _archived_root(tmp_path / "MockingBirdFieldAcceptanceY", fake_host=fake_host, tmp_path=tmp_path, tag="-y")
    (sibling / "runtime" / "otherhash").mkdir(parents=True)
    (sibling / "runtime" / "otherhash" / "big.dll").write_bytes(b"y" * 4096)

    execute_cleanup(dev_root=target, windows_host=fake_host, destroy=True)

    assert not target.exists()
    assert (sibling / "runtime" / "otherhash" / "big.dll").is_file()


# ---------------------------------------------------------------------------
# V8/V9 accumulation reproducer (governing brief §26) + stale-process
# reproducer (§27)
# ---------------------------------------------------------------------------


def test_v8_v9_reproducer_multiple_completed_archived_roots_are_reclaimable(
    fake_host: WindowsHost, tmp_path: Path,
) -> None:
    roots = [
        _archived_root(tmp_path / f"MockingBirdFieldAcceptanceV{n}", fake_host=fake_host, tmp_path=tmp_path, tag=f"-v{n}")
        for n in (4, 5, 6, 7)
    ]

    results = [assess_instance(dev_root=root, windows_host=fake_host) for root in roots]

    assert all(result.verdict == SAFE_TO_RECLAIM for result in results)
    assert all((result.reclaimable_bytes or 0) > 0 for result in results)


def test_v8_v9_reproducer_stale_still_running_instance_recommends_stop_first(
    fake_os: FakeOS, fake_host: WindowsHost, tmp_path: Path,
) -> None:
    """Represents V8's own disclosed state: a completed field-acceptance
    session's process left running, idle, long after the session ended."""

    root = tmp_path / "MockingBirdFieldAcceptanceV8"
    _make_deploy_tool_root(root, windows_host=fake_host, git_commit="8" * 40, build_id="build-v8")
    init_instance(dev_root=root, windows_host=fake_host)
    fake_os.start_listener(port=DEFAULT_PORT, git_commit="8" * 40, build_id="build-v8")

    result = assess_instance(dev_root=root, windows_host=fake_host)

    assert result.verdict == NOT_RECLAIMABLE_ACTIVE
    assert result.process_running is True
    assert "stop it first" in result.reason


# ---------------------------------------------------------------------------
# CLI (main()) -- argument parsing, dispatch, and exit-code conventions.
# ---------------------------------------------------------------------------


def test_cli_assess_exits_zero_even_when_not_reclaimable(
    fake_host: WindowsHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A determinate dry-run answer is success, not a tool failure --
    matches the module docstring's own exit-code contract."""

    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    monkeypatch.setitem(main.__globals__, "_dwd", lambda: _DWD)
    monkeypatch.setitem(_DWD, "real_windows_host", lambda: fake_host)

    exit_code = main(["assess", "--dev-root", str(root)])

    assert exit_code == 0


def test_cli_cleanup_dry_run_exits_zero_when_not_yet_reclaimable(
    fake_host: WindowsHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain dry-run (no --destroy) reporting "not reclaimable yet" is a
    correct, informative answer, not a failure."""

    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)  # active, not yet archived
    monkeypatch.setitem(main.__globals__, "_dwd", lambda: _DWD)
    monkeypatch.setitem(_DWD, "real_windows_host", lambda: fake_host)

    exit_code = main(["cleanup", "--dev-root", str(root)])

    assert exit_code == 0
    assert root.exists()


def test_cli_cleanup_destroy_exits_one_when_refused(
    fake_host: WindowsHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--destroy explicitly requested but correctly refused must exit
    non-zero -- a script/automation wrapping this call needs to be able to
    detect that the destructive action did not actually happen."""

    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    init_instance(dev_root=root, windows_host=fake_host)
    monkeypatch.setitem(main.__globals__, "_dwd", lambda: _DWD)
    monkeypatch.setitem(_DWD, "real_windows_host", lambda: fake_host)

    exit_code = main(["cleanup", "--dev-root", str(root), "--destroy"])

    assert exit_code == 1
    assert root.exists()


def test_cli_cleanup_destroy_exits_zero_when_it_actually_removes(
    fake_host: WindowsHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archived_root(tmp_path / "MockingBirdFieldAcceptanceX", fake_host=fake_host, tmp_path=tmp_path)
    monkeypatch.setitem(main.__globals__, "_dwd", lambda: _DWD)
    monkeypatch.setitem(_DWD, "real_windows_host", lambda: fake_host)

    exit_code = main(["cleanup", "--dev-root", str(root), "--destroy"])

    assert exit_code == 0
    assert not root.exists()


def test_cli_preflight_exits_one_when_insufficient(
    fake_host: WindowsHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceNew"
    monkeypatch.setitem(main.__globals__, "_dwd", lambda: _DWD)
    monkeypatch.setitem(_DWD, "real_windows_host", lambda: fake_host)
    monkeypatch.setitem(
        main.__globals__, "storage_preflight_report",
        lambda **_kwargs: _MODULE["StoragePreflightReport"](
            requested_root=str(root), resolved_root=str(root), probed_root=str(root),
            resolution_method="direct", platform="posix", filesystem_device_id=None,
            free_bytes=1, total_bytes=100, storage_health_tier="critical",
            recorder_max_bytes=1, reserve_bytes=1, required_bytes=2, known_reclaimable_bytes=0,
            known_reclaimable_instances=(), sufficient=False, reason="Insufficient storage for testing.",
        ),
    )

    exit_code = main(["preflight", "--dev-root", str(root), "--recorder-max-bytes", "1"])

    assert exit_code == 1


def test_cli_init_and_status_round_trip(fake_host: WindowsHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "MockingBirdFieldAcceptanceX"
    _make_deploy_tool_root(root, windows_host=fake_host)
    monkeypatch.setitem(main.__globals__, "_dwd", lambda: _DWD)
    monkeypatch.setitem(_DWD, "real_windows_host", lambda: fake_host)

    assert main(["init", "--dev-root", str(root)]) == 0
    assert main(["status", "--dev-root", str(root), "--json"]) == 0
    assert (root / MANIFEST_FILENAME).is_file()
