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

Four tiers, split purely by *where* a file lives inside the bundle
`build_local_product.py` already produces -- packaging itself is completely
unchanged:

- **app tier** -- `python/site-packages/mockingbird` (minus the nested
  `observation_runtime/` and `bioclip_runtime/` model bundles) and
  `mockingbird-*.dist-info`. Small, changes on every commit, always copied
  fresh into each release, never cached or shared.
- **Observation model tier** -- `python/site-packages/mockingbird/
  observation_runtime/`, the packaged MDv5 ONNX model + provider config.
  Changes only when the accepted model changes.
- **BioCLIP model tier** (Automatic Species Suggestion v1.2) --
  `python/site-packages/mockingbird/bioclip_runtime/`, the packaged BioCLIP
  2 model config/weights/labels/embedding cache. A second, fully
  independent model tier: its own content hash
  (`compute_bioclip_model_hash`), its own cache root
  (`BIOCLIP_MODEL_CACHE_DIRNAME`, a sibling of the Observation model's
  `models/` -- never the same directory namespace), its own junction into
  each release (`ensure_bioclip_model_cache`). A change to either model can
  never force an unnecessary re-copy of the other. Changes only when the
  accepted BioCLIP bundle changes.
- **runtime tier** -- everything else under `python/`: the embeddable
  CPython distribution plus every third-party dependency, including the
  ~1.3 GB ONNX Runtime GPU/CUDA/cuDNN stack and the ~150 MB optional
  BioCLIP dependency closure (torch/open_clip/...). Changes only when
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

## Real end-to-end findings (first actual `python scripts/deploy_windows_dev.py` run)

The hand-validation above exercised each `WindowsHost` mechanism in
isolation, in a disposable location, against a throwaway stand-in server --
deliberately not a real ~1.9 GB build, for the reasons the (now out-of-date)
"left for follow-up" note below used to give. That gap turned out to matter:
running the actual bare command, for the first time, against a real
integrated build produced five real, previously-unknown defects, none
reachable by the hermetic suite's own fakes and none exercised by the
isolated hand-validation above. All five are fixed; each is retained here
because each is exactly the shape of bug that only a real end-to-end run
against a real bundle can surface, and a future change in this vicinity
should re-read this before assuming the hermetic suite alone is sufficient
proof of correctness:

1. **`materialize_release` crashed on a bare-file top-level runtime-tier
   entry.** `typing_extensions` ships as a single `typing_extensions.py`
   file directly under `site-packages/`, not a package directory. The
   runtime-tier linking loop assumed every top-level entry it did not copy
   was a directory and unconditionally junctioned it; `New-Item -ItemType
   Junction` cannot target a file ("A directory is required for the
   operation"). Fixed by branching on `entry.is_dir()`, mirroring the
   `python/`-top-level-files loop just above it in the same function, and
   copying a bare-file entry from the cache instead of linking it.
   `make_bundle`'s fixture only ever synthesizes directory-shaped
   third-party packages, which is exactly why 89 passing hermetic tests
   never caught this.
2. **Junction removal silently targeted the shared cache instead of the
   release's own link.** WSL's drvfs surfaces an NTFS junction as a plain
   POSIX symlink on the Linux side (`stat`/`readlink -f` on an
   already-created junction reports `symbolic link`, target the junction's
   real target); `wslpath -w`, like `realpath`, transparently resolves
   through it. `_remove_junction_real` converted the *link's* WSL path
   directly, so every removal attempt actually asked Windows to `rmdir` the
   runtime/model **cache** directory, not the release's junction --
   non-destructive only by luck (`rmdir` with no `/s` refuses a real,
   non-empty directory), but it meant the removal always failed, exhausting
   every retry. Fixed by resolving the junction's *parent* (never itself a
   symlink, since this tool never nests one junction's target inside
   another) via `_to_windows_path_real` and appending the link's own name
   as a literal string, never letting `wslpath` see the symlink itself.
3. **`Start-Process -ArgumentList` handed `wscript.exe` an unquoted path
   containing a space.** Every release path ends in the literal filename
   `Start MockingBird.vbs`; `_ps_quote` only escapes PowerShell's own
   single-quote syntax, so the value handed to `-ArgumentList` reached
   `CreateProcess` with no surrounding double quotes and silently split
   into two arguments. `wscript.exe` then tried to run the first half as a
   script, failed to find it, and raised a blocking "Windows Script Host"
   error dialog -- confirmed directly via `Get-CimInstance Win32_Process`
   (the process's own received command line) and a `user32.dll`
   `EnumWindows` probe (a real window titled "Windows Script Host"
   belonging to that PID). Fixed by wrapping the path in an embedded,
   literal `"..."` pair inside the outer single-quoted PowerShell string --
   the same fix shape `_retrying_rmdir_powershell`'s own `cmd.exe` call
   already used for the same reason.
4. **`MOCKINGBIRD_HOME` was set to a WSL path, not a Windows one.**
   `launch_release` passed `str(userdata_dir)` -- WSL-visible, typically
   `/mnt/c/...` -- directly as the environment variable value, never
   through `to_windows_path`. Native Windows `pathlib` treats a bare
   `/mnt/c/...` string as *rooted but not absolute* (no drive letter), so
   it silently resolved relative to whatever drive the launched process's
   own current directory happened to be on (always the same drive as
   `%LOCALAPPDATA%`, since `Start MockingBird.vbs` sets
   `shell.CurrentDirectory` to the release directory) -- landing on a bogus
   `C:\mnt\c\Users\...\MockingBirdDev\userdata` sibling instead of raising.
   Confirmed directly: a live `mockingbird.sqlite3` and `mockingbird.log`
   turned up under that bogus path, real and currently open, while the
   documented `%LOCALAPPDATA%\MockingBirdDev\userdata` sat empty. Fixed by
   routing the value through `windows_host.to_windows_path` like every
   other cross-boundary path. No hermetic test caught it because the fake
   `WindowsHost.to_windows_path` is the identity function, so a bare
   `str(path)` and a real conversion happen to produce the same value
   there either way.
5. **`Start-Process -Wait` on `wscript.exe` never returns.** Proven by
   hand, repeatably: swapping `-Wait` for `-PassThru` plus a bounded poll
   on `$p.HasExited` completes in about a second with `ExitCode=0`; `-Wait`
   itself had still not returned after 180s, even though the launch fully
   succeeded within a couple of seconds every single time (the server came
   up healthy and reported the right identity moments later). Root cause:
   `shell.Run(..., 0, False)` inside the launcher starts `pythonw.exe`
   without giving it a fresh console of its own, so it inherits
   `wscript.exe`'s own (WSL-interop-spawned, so already somewhat unusual)
   console/handle set; `-Wait`'s underlying `Process.WaitForExit()` was
   observed to block until every process sharing those handles exits, not
   only `wscript.exe` -- and `pythonw.exe` is a long-running server never
   expected to exit on its own, so `-Wait` was never going to return, not
   merely slowly. Fixed by switching to `-PassThru` plus a short bounded
   poll, checking only whether the launcher script itself exited zero (its
   one real failure mode: `WScript.Quit 1` when `pythonw.exe` is missing);
   the actual confirmation that the server started is `verify_deployment`'s
   own bounded HTTP polling regardless, unaffected by this.
6. **The idempotent-redeploy path verified against a build identity it
   never wrote anywhere.** `deploy()` always calls `build_release_source`
   (never `accept_release_source`'s "read the identity already on disk"
   shortcut) for a plain `python scripts/deploy_windows_dev.py` invocation,
   which mints a fresh random `build_id` on *every* build regardless of
   whether the commit changed. When redeploying a commit whose release
   directory already exists, `deploy()` correctly reuses it rather than
   re-materializing -- but then verified the running instance against
   `source.build_id` (the fresh, throwaway one from the rebuild that was
   never applied to the reused directory) instead of `record.build_id`
   (the existing ledger entry, i.e. what the reused directory's own
   `build_info.json` actually contains) -- rejecting its own legitimate
   reuse, unconditionally, every time a commit was redeployed unchanged.
   The existing `test_deploy_redeploying_the_identical_commit_is_idempotent`
   never caught it: both of its `deploy()` calls go through
   `accept_release_source` against one fixed bundle, so `source.build_id`
   never changes between them either. Fixed by verifying against
   `record.build_id` unconditionally (identical to `source.build_id` in the
   fresh-materialize branch, correct in the reuse branch); added
   `test_deploy_redeploying_the_identical_commit_from_a_fresh_rebuild_is_idempotent`,
   which uses two bundles sharing a commit but not a `build_id` -- the
   actual shape of two independent real builds of the same commit -- and
   confirmed it fails on the old code with the identical real error message
   before confirming it passes on the fix.
7. **A mismatching runtime-cache entry was deleted *in place*, corrupting
   it.** Confirmed by real damage: validating a second real commit against
   an already-populated cache, `ensure_cache` decided the existing
   `runtime/<hash>/` entry no longer matched its own manifest and called
   `remove_tree` on it directly, in place -- while a still-running,
   legitimately-deployed release had files open straight out of that exact
   path via its own junction into it. `rmdir /s /q` deleted everything it
   could (2613 of 2626 files) and silently left the 13 it could not --
   every one of them a currently-loaded `.pyd`/`.dll` (Windows refuses to
   delete a loaded module) -- corrupting the cache entry for every release
   referencing it. Recovered by stopping the process (releasing the locks)
   and fully repopulating. Fixed by never deleting a mismatching entry in
   place: `ensure_cache` now renames it out of the way first (a
   same-volume rename does not require closing handles already open
   inside it, unlike deletion, so a process using files from here is
   completely undisturbed), populates and atomically renames the fresh
   entry into the real, trusted path, and only *then* best-effort-cleans
   up the renamed-away copy -- a failure there (still-locked files) can no
   longer corrupt what the trusted path itself points at.
8. **The mismatch in (7) was not corruption at all -- it was the running
   application itself, by entirely ordinary means.** Root-caused by direct
   comparison of the cache directory's actual contents against the fresh
   bundle's own runtime-tier file list: exactly 434 extra files, every
   single one a `__pycache__/*.pyc`, nothing else differed. The runtime
   cache is *junctioned*, not copied, into every release that shares it --
   so any file the running process itself writes through that junction
   (CPython writes a `.pyc` next to every `.py` it compiles, on first
   import, unless told not to) lands directly in the shared cache
   directory, not somewhere private to the release. A cache entry that
   actually gets *used* by a real, running release reliably grows past its
   own population-time manifest this way -- "once written, never modified
   again" was never quite true in practice once (7) is accounted for.
   Fixed at the source rather than only tolerating the resulting mismatch:
   `launch_release` now also sets `PYTHONDONTWRITEBYTECODE=1` for this dev
   tool's own launches, the same way it already sets `MOCKINGBIRD_HOME` --
   never a change to the real product's own packaging or its normal
   (non-dev-tool) startup behavior, which keeps writing `.pyc`s as usual.

All eight were found, root-caused, and fixed using the same real
WSL2/Windows/GPU interop as [[sandbox-has-windows-gpu-interop]] and
[[windows-onnxruntime-cuda-dll-loading-fix]] -- diagnostic scripts against
the actual packaged bundle, `Get-CimInstance`/`EnumWindows`/timed
reproductions, and direct before/after directory-content comparisons to
isolate each root cause precisely rather than guessing from symptoms, and a
full clean-slate `python scripts/deploy_windows_dev.py` run (twice, against
two real separate commits) that ended healthy, correctly identified, and
correctly rooted at `%LOCALAPPDATA%\MockingBirdDev\userdata` only after all
eight were fixed together.

### BioCLIP durable-deployment findings (Automatic Species Suggestion v1.2)

Two further real, empirically-reproduced findings, from actually building
the closure `WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS` needs rather than
inferring it from package metadata by eye -- see "BioCLIP runtime
packaging" in docs/local-product-packaging-design.md for the full design
these two closed:

9. **A second `pip install --target` call into an already-populated
   site-packages does not consult what is already on disk.** Its
   dependency *resolution* step always resolves purely against the
   index/`--find-links` source, independent of the target directory's
   current contents -- the target is only consulted, file-by-file, at the
   final unpack step, where an already-existing file is left untouched
   (never overwritten) but a *new*, differently-named `.dist-info/`
   directory is still written unconditionally. Reproduced for real:
   installing the exact `WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS` closure (via
   `torchvision`'s own loosely-bounded `pillow` dependency) into a
   site-packages that already had the core tier's `Pillow==11.3.0`
   installed resulted in *both* `pillow-11.3.0.dist-info/` (real, matching
   the actual `PIL/` code on disk) and a freshly-resolved
   `pillow-12.3.0.dist-info/` (metadata only, no matching code) sitting
   side by side -- an ambiguous, indeterminate-which-version-wins install
   that `importlib.metadata.version(...)` has no defined tiebreak for.
   Fixed two ways: every package the BioCLIP closure shares with an earlier
   tier is now exact-pinned to precisely that tier's own resolved version
   (turning the later call into a genuine no-op for it), and new
   `verify_no_duplicate_site_packages_metadata` fails the whole build
   outright if this shape ever recurs regardless of cause, scanning for any
   PEP 503-normalized package name with more than one `.dist-info/`.
10. **Offline `--find-links ... --no-index` resolution requires every
    package to be named explicitly, even ones "owned" only transitively.**
    A plain online resolution of the pinned closure silently resolves
    `anyio==3.7.1`'s own `sniffio>=1.1` dependency without it being named
    anywhere -- but the exact same pinned list, installed offline against a
    local wheel cache that does not happen to also contain a `sniffio`
    wheel, fails outright ("No matching distribution found for sniffio"),
    reproduced for real while validating `DEFAULT_BIOCLIP_WHEEL_CACHE_DIR`.
    Every package the offline path needs -- including ones no line in
    `WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS` "conceptually" owns -- must be
    named in that same list for the cache to be self-sufficient; `sniffio`
    is now pinned there explicitly for exactly this reason.

Both were caught by (and are the reason for) `test_real_windows_bioclip_
dependency_closure_installs_offline_with_no_duplicates` in
tests/test_local_product_packaging.py, which really installs the full
pinned closure from the local wheel cache and asserts zero duplicates --
skipped, never failed, on a build host without that cache.

## Left for follow-up (deliberately out of scope here)

- ~~**Cache garbage collection.** `--keep` bounds *release* directories
  only; a runtime/model cache entry no retained release still references is
  never automatically removed. Given the cache is small in count (one entry
  per distinct dependency/model version actually built, not per commit)
  this is unlikely to matter in practice; a bounded `--gc-cache` pass (walk
  every retained release's recorded `runtime_hash`/`model_hash`, remove any
  cache directory none of them reference) would be a natural, self-contained
  addition later.~~ -- **closed, Storage / Retention / Disk-Pressure &
  Recovery Closure v1**: the "unlikely to matter in practice" judgment was
  wrong. Real measurement on this project's own real dev machine found 21
  never-pruned entries under `RUNTIME_CACHE_DIRNAME` alone (~38.5 GB,
  including 6.25 GB of definite orphaned `.staging-*`/`.stale-*` leftovers
  from interrupted cache populations) -- the single largest disk consumer
  found anywhere in that investigation, and the dominant, dated,
  directly-quantified driver of a real observed Windows Host `C:`
  free-space decline. `gc_cache_command`/`--gc-cache` now implements
  exactly the shape predicted above (referenced-hash walk over every
  currently-on-disk retained release, plus an unconditional
  `.staging-*`/`.stale-*` sweep) -- see
  [storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md).
- **A native Windows robocopy path for first-time cache population.** The
  one unavoidable full-size transfer (populating a cache entry for a new
  runtime/model hash) currently copies file-by-file from WSL Python
  (`shutil.copy2` per file, via the `WindowsHost.copy_file`/`ensure_dir`
  seam) rather than shelling out to a multithreaded native `robocopy`
  reading over the WSL UNC path from the Windows side. Simpler and already
  correct; a real optimization opportunity if this one-time cost is ever
  measured and found too slow in practice.
- ~~Real native-Windows execution of this tool itself... not end-to-end
  with a real ~1.9 GB build~~ -- superseded: a real, clean-slate
  `python scripts/deploy_windows_dev.py` end-to-end run, against a real
  ~1.9 GB build on real native Windows with a real GPU, was completed after
  all -- this sandbox has genuine WSL2/Windows/GPU interop (see
  [[sandbox-has-windows-gpu-interop]]), the same access that made
  `af15161`/`60928815e5` possible. It found and fixed five real defects
  -- see "Real end-to-end findings" above -- that neither the hermetic
  suite nor the isolated hand-validation elsewhere in this document could
  have caught. The final native-Windows *product* smoke (camera, live
  detection, a real Visit) is still a separate, deliberately-out-of-scope
  handoff -- this tool's own job is proven; MockingBird's product behavior
  on a real bird is not this tool's concern to verify.

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

BioCLIP durable-deployment (Automatic Species Suggestion v1.2) additionally
touched: `scripts/deploy_windows_dev.py` (second, independent BioCLIP model
cache tier; `WindowsHost.run_bioclip_runtime_check`/`verify_bioclip_
runtime`/`BioClipRuntimeVerification`; CLI passthrough flags),
`scripts/build_local_product.py` (BioCLIP dependency closure/model bundle
packaging, `verify_no_duplicate_site_packages_metadata`), new
`src/mockingbird/species/bioclip_runtime.py`, `repository/product_
repository.py` (`_bioclip_config` only), `tests/test_deploy_windows_dev.py`,
`tests/test_local_product_packaging.py`, new `tests/test_bioclip_
runtime.py`, and this document plus docs/local-product-packaging-design.md's
own "BioCLIP runtime packaging" section.

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
