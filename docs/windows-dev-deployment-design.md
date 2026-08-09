# Windows Dev Deployment Workflow

**What this is:** developer tooling only. It automates deploying a real
Windows local-product build from a WSL checkout to a dedicated Windows
development location, replacing a manual, error-prone loop with one command.
It changes nothing about how MockingBird itself behaves for a real user; see
[local-product-packaging-design.md](local-product-packaging-design.md) for
that (unchanged) product packaging design, which this reuses rather than
duplicates.

**Why this is needed:** validating a real native-Windows build (the ~1.9 GB
artifact `scripts/build_local_product.py` produces, including the embedded
Python, ONNX Runtime GPU, and CUDA/cuDNN stack) previously meant: build a
ZIP, copy it through `/mnt/c` from WSL, manually delete the old extraction,
extract the new one, sometimes accidentally launch the *old* build, inspect
port 8000 to guess which commit is actually running, manually launch the
`.vbs` launcher, and manually decide whether it worked. This is exactly the
kind of manual process that let a real defect (the packaged CUDA DLL closure
bug fixed in `af15161`) reach a native-Windows acceptance pass instead of
being caught earlier and more cheaply.

## One-command usage

```
python scripts/deploy_windows_dev.py                  # build + deploy HEAD
python scripts/deploy_windows_dev.py --commit <ref>    # verify a specific already-checked-out commit
python scripts/deploy_windows_dev.py --artifact <path> # deploy an already-built bundle dir or .zip
python scripts/deploy_windows_dev.py --rollback        # stop current, launch the previous retained release
python scripts/deploy_windows_dev.py --status          # read-only report; makes no changes
python scripts/deploy_windows_dev.py --keep 3          # bounded cleanup: keep only the 3 most recent releases
```

`--commit` **verifies** what is already checked out; it never runs `git
checkout` on an operator's behalf. `build_local_product.py` always builds
whatever is currently at `HEAD` -- if the resolved `--commit` does not match
`HEAD`, the tool refuses before any build work starts.

## Release layout

```
%LOCALAPPDATA%\MockingBirdDev\
    userdata\                          <- ONE shared dev data directory, every release, forever
    runtime\<runtime-hash>\python\...   <- embeddable Python + every third-party dependency (~1.3 GB)
    models\<model-hash>\...             <- the packaged MDv5 ONNX model + provider config (~500 MB)
    releases\
        deployments.json                <- append-only ledger: every deploy this tool ever made
        current.json                    <- which release this tool most recently started, and its PID
        <git-short-sha>\
            release_info.json           <- this tool's own record of what it deployed here
            Start MockingBird.vbs       <- real, fresh copy (unmodified from build_local_product.py)
            README-FIRST.txt            <- real, fresh copy
            python\
                python.exe, pythonw.exe, python312.dll, python312.zip, python312._pth   <- real, fresh copies (tiny)
                site-packages\
                    mockingbird\                          <- real, fresh copy (the app itself)
                        build_info.json                     <- self-reported git commit / build id
                        observation_runtime\  --[NTFS junction]--> ..\..\models\<model-hash>\
                    mockingbird-<version>.dist-info\        <- real, fresh copy
                    fastapi\  --[NTFS junction]--> ..\..\..\..\runtime\<runtime-hash>\python\site-packages\fastapi
                    onnxruntime\, numpy\, nvidia\, ...  --[NTFS junctions, same pattern]
```

Structurally identical to what `build_local_product.py` itself produces --
same relative paths throughout `python/...` -- so a dev deployment tests the
exact directory shape a real end user's unzipped bundle has. The only
difference is that the large, rarely-changing parts (the interpreter and
every third-party dependency, and the packaged model) are backed by shared,
immutable, hash-verified cache directories via NTFS junctions instead of
separate copies; the small, always-changing app tier
(`mockingbird`/`mockingbird-*.dist-info`, plus the top-level launcher/readme
and a handful of tiny interpreter files that cannot be junctioned
individually) is always a real, fresh copy.

## Runtime/model cache

Three tiers, split purely by *where* a file lives inside the bundle
`build_local_product.py` already produces -- packaging itself is completely
unchanged:

- **app tier** -- `python/site-packages/mockingbird` (minus the nested
  `observation_runtime/` model bundle) and `mockingbird-*.dist-info`. Small,
  changes on every commit, always copied fresh into each release, never
  cached or shared.
- **model tier** -- `python/site-packages/mockingbird/observation_runtime/`,
  the packaged MDv5 ONNX model + provider config. Changes only when the
  accepted model changes.
- **runtime tier** -- everything else under `python/`: the embeddable
  CPython distribution plus every third-party dependency, including the
  ~1.3 GB ONNX Runtime GPU/CUDA/cuDNN stack. Changes only when
  `EMBED_PYTHON_VERSION` or a pinned dependency version changes.

Each tier's cache key is a real SHA-256 over every file's own content
(relative path, per-file hash, and size, combined deterministically) --
`compute_runtime_hash`/`compute_model_hash` in `scripts/deploy_windows_dev.py`
-- never a version-string shortcut, so it reflects the *actual bytes*
regardless of how they got there.

**Reuse and integrity** (`ensure_cache`): a cache entry lives at
`<cache_root>/<content_hash>/` -- content-addressed, so "automatic reuse only
when hashes match" and "safe rebuild when versions change" both fall directly
out of the naming scheme. Population is staged into a sibling
`<hash>.staging-<random>/` directory and atomically renamed into place only
once fully populated -- an interrupted population can never leave a partial
directory sitting at the trusted, hash-named path. On reuse, the *cache
directory's own manifest* is checked against a fresh, cheap structural count
(file count + total bytes) of what is *actually, currently* present in the
directory -- not only against what the manifest claims -- so a cache entry
whose name still matches but whose content was tampered with, partially
deleted, or corrupted (an early implementation of this check had exactly that
gap: it compared the fresh bundle's expected stats only against the cache's
*stored claim*, never against the directory's real contents, so silent
corruption was invisible to it) is detected and rebuilt, never silently
trusted. This never re-hashes a cache entry's full content on every reuse --
that would defeat the purpose of caching -- the expensive cryptographic hash
is always computed fresh on the small/source side, which the caller needs
regardless of whether reuse ends up being possible.

**Immutability and junction safety**: once written, a cache directory is
never modified in place, and cleanup (`--keep`) never deletes a cache entry
at all -- only release directories are bounded (see Cleanup below). Every
junction a release creates is recorded by its own relative path at
materialization time; removing a release later unlinks exactly those
recorded junctions individually (native `cmd.exe /c rmdir` on the reparse
point, no `/s`) *before* recursively deleting whatever real content remains
-- verified empirically (see "WSL/Windows interop notes" below) that this
never touches the junction's target, and native `rmdir /s` is used for the
bulk delete rather than PowerShell's `Remove-Item -Recurse`, which has real
historical bugs around reparse points.

## Exact build identity

`scripts/build_local_product.py` mints a `BuildIdentity` for every build
(`git_commit`, a random-per-build `build_id`, `built_at`, `app_version`) and
writes it into the bundle itself
(`python/site-packages/mockingbird/build_info.json`, next to the installed
package -- the same "packaged asset next to this installed package"
convention `web_dist`/`observation_runtime` already use) via
`write_build_identity`, and records the same identity in `manifest.json`.
`build_id` is a fresh random token per *build*, not per *commit* -- two
builds of the exact same commit (a rebuild after an unrelated local fix)
still get different `build_id`s.

At runtime, `mockingbird.runtime_state.resolve_build_identity()` reads that
file back (resolved from the installed package's own location, never
`os.getcwd()`), and `GET /api/product/instance` (`ProductInstanceIdentity`)
now reports `git_commit`/`build_id` alongside the existing `instance_id`/
`app_version`. `(None, None)` for anything that never went through a real
packaged build (a bare development checkout, every ASGI-transport test) --
the same conservative "cannot confirm" default `resolve_instance_id` already
established, never a guess. This is API-only, additive, and does not touch
the basic product UI, per the milestone's own instructions.

## Deployment verification

After launch, `verify_deployment` polls (bounded by `--timeout`, default 90s)
until the deployed instance is healthy and self-reports **both** the exact
expected `git_commit` **and** `build_id` -- matching on commit alone would
not prove "old build cannot masquerade as new" (a rebuild of the same commit
still has to be provably the *new* build, not a still-running old one). It
then also checks the port-owning process's own OS-reported executable path is
under either the release directory or its runtime cache (accepting either,
since an NTFS junction's reported path can resolve to either the logical or
the physical location depending on Windows/PowerShell version -- both are
correct), and finally that `/api/product/health` answers with a well-formed
body and a valid `database_schema_version`. It deliberately never requires
`ready: true` -- a fresh dev instance honestly reporting "no camera
configured yet" is a successful *deployment*, not a failure; this tool
verifies the deployment, never the product's own onboarding state.

Every failure path names the specific fact that did not check out (never
became healthy / wrong commit / wrong build / wrong executable path / invalid
schema health) so a failure is always actionable, never a bare timeout.

## Running-instance safety

The helper never identifies "mine to stop" by port alone. `stop_verified_
deployment` requires a **fresh, live re-check** (never a merely-recorded PID)
proving the current occupant of the port is:

1. answering a real, healthy MockingBird `/health` **and** `/api/product/instance`;
2. self-reporting a `git_commit`/`build_id` pair that matches an entry in
   this tool's own append-only ledger (`verified_owning_release`).

Both checks must pass. Anything else -- an arbitrary process, `wslrelay.exe`,
WSL MockingBird forwarded to this port, a real production MockingBird
install, another tool's own build, or an old build of the *same* commit with
a different `build_id` -- raises `DeploymentError` and stops nothing. Only
after both checks pass is the recorded PID terminated
(`Stop-Process -Force`), with a bounded wait for real exit.

## User data / Camera Node pairing / Visits / truth

`launch_release` always sets `MOCKINGBIRD_HOME` to one fixed path,
`%LOCALAPPDATA%\MockingBirdDev\userdata\` -- **never** the real product
default (`%LOCALAPPDATA%\MockingBird`, `mockingbird.runtime.
resolve_runtime_home`'s own unmodified default) -- and **never** per-release.
This one environment variable is the entire mechanism behind three
requirements at once:

- a real production install on the same machine is structurally untouched
  (different directory, full stop);
- Camera Node pairings, reviewed Visits, and every other local fact a
  developer builds up while testing persist across every redeploy and
  rollback, regardless of which commit is currently running -- never reset
  merely because the running code changed;
- rollback needs no special-case data handling at all: the dev database was
  never per-release in the first place.

(The environment-variable-through-`wscript.exe`-through-`Start MockingBird.vbs`
inheritance chain was verified empirically against a real WSL2/Windows host
while designing this -- see below.)

One real product-level caveat this tool does not paper over: if a later
commit's own database migration moves the shared dev database's schema
forward, then `--rollback` to an *older* commit against that now-newer schema
is a genuine backward-compatibility question the product itself already
owns (`DatabaseSchemaCompatibilityError`) -- `verify_deployment` will
honestly report the failure (the process fails to start, or reports unhealthy)
rather than silently succeeding or attempting a data migration of its own.

## Rollback

`--rollback` re-establishes "current" from a fresh live probe (never solely
the recorded pointer file, in case a release was started or stopped outside
this tool), finds the most recently deployed *other* release whose directory
still exists (ledger append order, not wall-clock timestamps -- see below),
applies the exact same stop-safety proof as any other stop, launches that
release, and verifies its build identity the same way a fresh deploy does.

## Cleanup

`--keep N` (or `--cleanup`, defaulting to keep 5) removes release
directories beyond the most recent `N`, always additionally protecting the
current release and its immediate rollback target regardless of `N` -- even
`--keep 0` can never remove either. "Most recent" is the ledger's own append
order, not a sort by the `deployed_at` timestamp *string* -- an early version
of this logic did the latter and could genuinely misorder two deploys made
within the same wall-clock second (routine in fast/scripted iteration),
silently keeping the wrong release. Cleanup is bounded to release
directories only: it never touches the runtime/model cache (garbage
-collecting an orphaned cache entry nothing references any more is a
reasonable follow-up, deliberately left out of this bounded pass -- see
"Left for follow-up" below), the shared `userdata/` directory, or anything
outside `releases/`.

## Reused, not duplicated

Every actual packaging step -- wheel build, embeddable-Python assembly,
`WINDOWS_RUNTIME_REQUIREMENTS`/`WINDOWS_GPU_RUNTIME_REQUIREMENTS` install,
`verify_windows_gpu_runtime_dll_closure`, `package_observation_runtime_assets`
(model SHA/provenance verification), `verify_clean_tracked_source`
(clean-source build requirement), `write_manifest`/checksum generation --
comes from calling `scripts/build_local_product.py`'s own public functions
directly (loaded via `runpy.run_path`, the same mechanism the existing test
suite already uses for it, since `scripts/` is deliberately not a package).
Nothing in `deploy_windows_dev.py` re-implements or bypasses any of it. The
one small, incidental fix made to `build_local_product.py` itself: `output_dir`
is now resolved to an absolute path as the very first thing `build_local_
product()` does (see `[[build-local-product-relative-output-dir-bug]]` --
a still-open bug where a relative `output_dir` could resolve against two
different directories -- the release-build subprocess's own `cwd` vs. this
process's cwd for a later existence check -- silently losing the built wheel).

**The production ZIP remains independently self-contained.** Nothing in
`deploy_windows_dev.py` ever mutates a source bundle it reads from -- every
cache-population and release-materialization function only *reads* from
`bundle_dir` and *writes* to a separate cache/release directory (see
`test_deploying_never_mutates_the_source_bundle`). A real build produced for
end-user distribution is completely unaffected by whether this dev tool ever
runs against it.

## WSL/Windows interop notes

An early validation pass found that this environment's loopback traffic from
WSL directly to a Windows-bound TCP listener is not reliably reachable
(neither `127.0.0.1` nor the WSL-reported default-route host IP accepted a
connection to a real Windows-side listener in that test), even though plain
Windows-native loopback (a Windows process talking to another Windows process
on `127.0.0.1`) works normally. Rather than depend on WSL2's bidirectional
-localhost-forwarding configuration (which varies across Windows/WSL versions
and local network policy), **every** operation that must observe the real
Windows process -- HTTP health/identity polling, port-owner PID lookup,
process liveness/kill, junction creation/removal -- runs as a **Windows
-native PowerShell process**, invoked through the same WSL/Windows interop
already used to launch the app itself (`powershell.exe -File <windows-path>`,
never an inline `-Command` string across three shells, which was empirically
a source of real quoting bugs while designing this). This is also simply more
representative: it is the same vantage point a real user's double-click
launch is observed from.

All of that lives behind one `WindowsHost` seam
(`scripts/deploy_windows_dev.py`) -- every orchestration function above it is
otherwise pure/hermetic and takes a `WindowsHost`, the same injectable
-dependency pattern `build_local_product.py` already uses for its own
real-vs-test installers. `real_windows_host()` is the only production
implementation; the test suite always supplies an entirely in-memory fake
backed by a plain temp directory tree and a simulated Windows process/port
table, never a real `powershell.exe` call.

Verified by hand against a real WSL2/Windows host while designing this
(outside the automated suite, the same way `build_local_product.py`'s own
real end-to-end packaging run was validated once by hand rather than
re-run on every test invocation) -- including a genuine end-to-end pass of
`real_windows_host()` itself: a throwaway Windows-native `python.exe` HTTP
server (this machine's real system Python, independent of any MockingBird
build) stood in for a running MockingBird instance, and every real
`WindowsHost` function (`_http_get_real`, `_port_owner_pid_real`,
`_process_alive_real`, `_process_image_path_real`, `_kill_process_real`,
`_make_junction_real`, `_remove_junction_real`) was exercised against it for
real, not mocked -- all in a disposable `%TEMP%` location, never touching
`MockingBirdDev` or any real product path:

- `Invoke-WebRequest`/`ConvertTo-Json` round-trips a real HTTP response
  (status, JSON body) back through `_http_get_real` correctly, including
  the connection-refused case (nothing listening) reporting `ok=False`
  rather than raising.
- `Get-NetTCPConnection` finds the real owning PID of a real listening
  port; `Get-Process`/`Stop-Process` correctly report liveness, the real
  `python.exe` image path, and terminate the process -- confirmed
  `process_alive` reports `False` immediately after.
- `New-Item -ItemType Junction` creates a real NTFS junction without
  elevation or Developer Mode; reading through it works transparently, and
  its target's content survives the junction being removed.
- An environment variable set in the launching PowerShell process propagates
  correctly through `wscript.exe` -> the `.vbs`'s own `shell.Run` -> the
  spawned child process -- confirmed the exact chain `launch_release` uses
  for `MOCKINGBIRD_HOME`.

**A genuine, reproducible finding from this pass, and why junction removal
is retried and verified rather than trusted on the first attempt:**
`cmd.exe /c rmdir "<junction>"` (no `/s`) reliably removes only the reparse
point, never the target's content, matching documented native Windows
`rmdir` behavior (`PowerShell`'s own `Remove-Item -Force` on a junction, by
contrast, threw a spurious `NullReferenceException` in this environment's
PowerShell version -- avoided entirely by never using it). But reading a
junction's content through its **WSL-side (drvfs) view** measurably holds
it busy afterward: an immediately-following *native Windows* `rmdir` of
that same junction reliably failed (reproduced across repeated runs, and
persisted for several seconds -- not cleared by a bounded few-hundred
-millisecond retry). Creating a junction and removing it immediately with
**no** WSL-side read in between -- this tool's own real code path, since
`materialize_release` only ever creates a junction and the running
MockingBird process only ever reads its own files natively on the Windows
side, never through WSL -- succeeded instantly and reliably across every
repeated run. `_remove_junction_real`/`_remove_tree_real` still retry
(bounded, ~3s worst case) and explicitly verify via a final `Test-Path`
rather than trusting a bare `cmd.exe` exit code either way: cheap insurance
against the same general shape of transient contention (antivirus, the
Windows Search indexer) that is well-documented on Windows generally, even
though this tool's own usage pattern was not observed to need it.

## Left for follow-up (deliberately out of scope here)

- **Cache garbage collection.** `--keep` bounds *release* directories only;
  a runtime/model cache entry no retained release still references is never
  automatically removed. Given the cache is small in count (one entry per
  distinct dependency/model version actually built, not per commit) this is
  unlikely to matter in practice; a bounded `--gc-cache` pass (walk every
  retained release's recorded `runtime_hash`/`model_hash`, remove any cache
  directory none of them reference) would be a natural, self-contained
  addition later.
- **A native Windows robocopy path for first-time cache population.** The
  one unavoidable full-size transfer (populating a cache entry for a new
  runtime/model hash) currently copies file-by-file from WSL Python
  (`shutil.copy2` per file, via the `WindowsHost.copy_file`/`ensure_dir`
  seam) rather than shelling out to a multithreaded native `robocopy`
  reading over the WSL UNC path from the Windows side. Simpler and already
  correct; a real optimization opportunity if this one-time cost is ever
  measured and found too slow in practice.
- Real native-Windows execution of this tool itself (not just the packaging
  it wraps) was validated by hand against a real WSL2/Windows host for the
  specific mechanisms above, not end-to-end with a real ~1.9 GB build --
  the same "final native-Windows smoke is handed off" pattern this
  repository's own packaging design doc already uses, for the same reason
  (this sandboxed session cannot execute a native Windows binary or spend
  the several minutes/network access a real build requires).

## Non-goals

No detector, CUDA/runtime dependency, Camera Node, pairing, or Observation
Engine behavior changes; no frontend redesign; no end-user updater,
installer/MSI, or cloud deployment. This phase does not change what
`scripts/build_local_product.py` ships -- only how an already-built (or
freshly built) artifact gets deployed to, and identified on, a Windows
development machine.

## Files touched

- `scripts/deploy_windows_dev.py` (new) -- the deployment tool itself.
- `scripts/build_local_product.py` -- `BuildIdentity`/`write_build_identity`,
  `manifest.json`'s new `build_identity` key, and the `output_dir`
  absolute-path fix.
- `src/mockingbird/runtime_state.py` -- `resolve_build_identity`/
  `_build_info_path`.
- `src/mockingbird/api/schemas.py`, `api/main.py` -- `ProductInstanceIdentity`
  gains `git_commit`/`build_id`.
- `tests/test_deploy_windows_dev.py` (new), `tests/test_local_product_
  packaging.py`, `tests/test_windows_launcher_instance_identity.py`.
- This document.

## Validation tier

Tier 2 (domain integration touching a shared API schema) at minimum for the
`ProductInstanceIdentity`/`build_local_product.py` changes; the deployment
tool itself is developer tooling with no product surface, validated by its
own hermetic test suite. Run: the full backend test suite (`pytest tests/`,
unaffected by this change beyond the new/extended files above), and the
focused new suites directly
(`pytest tests/test_deploy_windows_dev.py tests/test_local_product_
packaging.py tests/test_windows_launcher_instance_identity.py`). No frontend
change is in scope (`ProductInstanceIdentity` has no frontend consumer --
`/api/product/instance` is documented as launcher/developer-tool-only), so no
frontend type-check/build is required. No hardware, camera, or Observation
Engine runtime behavior is exercised or required.
