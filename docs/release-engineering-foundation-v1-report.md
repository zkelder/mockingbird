# Release Engineering Foundation — Native-Windows Clean Install, Upgrade & Recovery Closure v1

**Roadmap phase:** Lane P (Release Engineering Foundation / Distribution) and
Lane L (Appliance / Update / Recovery) in
[release-execution-state.md](release-execution-state.md).

**Starting accepted state:** branch `main`, HEAD `64f787c`, schema `v53`,
latest accepted milestone "Acoustic Productization, Licensing & Field
Acceptance v1." Production detector MDv5a ONNX @ `0.1`; production visual
identification BioCLIP-2 + Identification Eligibility/Abstention. None of
those decisions were reopened by this milestone.

## Governing-doc reconciliation

`docs/release-execution-state.md` still recorded accepted HEAD `02af3f4`
and "Current authorized implementation milestone: NONE" (a New-ChatGPT-
Project transition checkpoint) at the time this milestone started, even
though a later commit (`64f787c`, itself just scheduler bookkeeping) had
already landed. This milestone's own governing task explicitly authorized
"Release Engineering Foundation — Native-Windows Clean Install, Upgrade &
Recovery Closure v1" directly and instructed reconciling the file's stale
HEAD/authorization bookkeeping at closure without altering any accepted
decision -- that reconciliation is recorded in the "Closure update" section
below, not treated as a gap this milestone needed to resolve itself.

## Concurrent-writer verification

Before any change, `ListAgents` found five other interactive Claude Code
sessions attached to this same working tree (ages 22 minutes to 8 hours).
Per this repository's own "Concurrent writers" rule, each was pinged
directly; all five confirmed idle, working-tree-clean, and safe to proceed
before implementation began. See the session transcript for the individual
confirmations.

## Repository findings before implementation

Investigated via three parallel read-only agents plus direct reading of
`docs/product-doctrine.md`, `docs/roadmap.md`,
`docs/local-product-packaging-design.md`, `docs/local-backup-recovery-
design.md`, `docs/single-app-runtime-recovery-design.md`, and
`docs/using-mockingbird.md`.

**Already solid, not reopened:**

- `scripts/build_local_product.py` produces a real, validated,
  self-contained "unpack and run" Windows bundle: clean-tracked-source
  guard (`verify_clean_tracked_source`/`export_clean_source_tree`, refuses
  a dirty tree by default), frontend-freshness SHA-256 fingerprinting,
  SHA-256-verified MDv5/BioCLIP-2 model bundle copying against accepted
  hashes (never downloaded/committed), pinned GPU/CUDA runtime, a
  build-time BirdNET non-commercial-license redistribution guard
  (`verify_no_nc_licensed_acoustic_model_redistribution`), and a
  deterministic, byte-identical zip with `manifest.json`/`SHA256SUMS`
  including real git-commit provenance (`build_identity.git_commit`,
  `source_state`).
- The runtime home (`%LOCALAPPDATA%\MockingBird`) is structurally separate
  from the install folder -- replacing the app bundle does not touch
  userdata by construction, not merely by convention.
- The schema-migration runner (`storage/database.py`) is real, automatic
  on every startup, and already genuinely transactional: the entire
  pending migration chain for one startup commits or rolls back as one
  unit (`_run_migrations_with_transactional_ddl`), proven by a pre-existing
  test (`test_a_mid_chain_migration_failure_rolls_back_every_step_not_
  only_its_own`) that a mid-chain failure leaves *no* partially-applied
  table behind, not only the failing migration's own.
- Backup/restore (`storage/backup.py`) is real, atomic, and verified:
  online SQLite backup API, zip archive with per-file SHA-256, an
  automatic `kind="pre_restore"` safety snapshot before any restore, and a
  hard-kill-mid-restore sentinel (`detect_interrupted_restore`) already
  proven recoverable.
- `runtime.py`'s `run_preflight`/`--check` already fails closed on a
  genuine schema incompatibility before the app ever binds a port or
  serves a request.
- Host↔Camera Node **wire-protocol** compatibility (`api_version`,
  `transport_protocol_version`) is already hard-gated and refuses on
  mismatch, at pairing time and per-transport-call respectively.

**Confirmed real gaps, closed by this milestone:**

1. **No automatic backup before a forward schema migration.** Migrations
   ran automatically and silently on next launch after replacing app
   files, with no safety net unless a user manually created a backup
   first (nothing prompted them to). This is precisely what
   `docs/appliance-storage-privacy-recovery-v1-contract.md`'s own "Bounded
   update-readiness review (Phase O)" section had already identified and
   explicitly deferred: *"Rollback for a future managed upgrade would
   need: a pre-upgrade backup trigger... a health check after migration
   but before declaring the upgrade successful... This remains future
   work, correctly scoped as its own future milestone, not started
   here."* That review even predicted the exact mechanism used below.
2. **No genuine post-migration health check.** A migration completing
   without raising an exception only proved no exception happened, not
   that the resulting database actually passed its own integrity check.
3. **No coherent "upgrade" operation, anywhere, and no documentation of
   one.** `docs/using-mockingbird.md` documented install/first-run/backup/
   restore/troubleshooting but had no upgrade section at all.
4. **No CI automation of any kind.** `.github/workflows/` did not exist.
5. **No `LICENSE` or `SECURITY.md`.** Confirmed genuinely absent (`ls`
   returned nothing for either), matching Gate F's own recorded
   disposition.
6. **Version-string drift risk.** Four independently hand-typed `"0.1.0"`
   literals (`pyproject.toml`, `mockingbird.__version__`'s fallback,
   `mockingbird_node.__version__`'s fallback, the FastAPI `app`'s own
   `version=`), with no test catching drift if one were bumped without the
   others -- undermining "verify resulting health/version compatibility"
   for exactly the moment (right after an upgrade) that fact matters most.
7. **The Host release manifest had weaker structured provenance than the
   Camera Node's own manifest.** `git_commit` is populated in *both* the
   clean and `--allow-dirty-source` build paths (a real commit hash
   either way), so it is not itself a cleanliness signal; only the
   top-level `source_state` string's `"git:"`/`"dirty:"` prefix
   distinguished them, requiring a consumer to parse a string rather than
   check a field. `scripts/build_camera_node_artifact.py`'s manifest
   already carries an explicit `source_clean` boolean.
8. **No release-artifact smoke test, in CI or otherwise.**
9. **A real, currently-live packaging-dependency-closure defect** --
   found only once this milestone's own validation reached genuine
   native-Windows acceptance (not during initial repository investigation,
   which cannot see a missing runtime dependency from source alone): the
   packaged Windows bundle could not start at all. `pyproject.toml`'s core
   `dependencies` had gained `astral` (Environmental Context Foundation
   v1), but `scripts/build_local_product.py`'s separately-maintained
   `WINDOWS_RUNTIME_REQUIREMENTS` mirror was never updated to match --
   `ModuleNotFoundError: No module named 'astral'`, raised from
   `product_repository.py`'s own unconditional import chain, before the
   app ever bound a port. This was a real, currently-shipping defect in
   the accepted codebase, not something this milestone's own feature work
   introduced -- exactly the "prerequisite correctness defect" case the
   governing task's own instructions anticipated, root-caused and fixed
   (commit `248853a`) because it directly blocked this milestone's own
   acceptance goal. See "Native-Windows acceptance," below, for how it was
   found, and its own regression test
   (`test_windows_runtime_requirements_matches_every_pyproject_core_
   dependency`) for durable, general protection against this exact class
   of drift recurring with any future dependency.

**Investigated, found not to need a code change:**

- **FFmpeg packaging.** Confirmed genuinely not bundled, not a pip
  dependency, not fetched by the build script -- an end user needs it
  installed separately (on PATH, or a configured path) for RTSP/ONVIF/USB/
  DirectShow live playback, offline video import, and audio capture.
  Doctor already reports this honestly (a `WARN`, never silent, with a
  plain-language remediation). The recommended, first-listed camera type
  (a paired MockingBird Camera Node) does not need ffmpeg at all, so a
  clean machine can still reach a healthy core Local-Only product without
  it. Full bundling would require its own licensing research (which
  ffmpeg build, which license terms permit redistribution) closer in
  shape to the already-completed BirdNET licensing work than to a bounded
  packaging fix -- deliberately deferred, not silently dropped. Instead:
  Doctor's existing message now links to where to get it
  (`https://ffmpeg.org/download.html`) and notes the Camera Node path
  doesn't need it, and `using-mockingbird.md`'s "Add a camera" section now
  says the same thing before a user hits a confusing failure.
- **`LICENSE`.** Genuinely absent, confirmed. Its disposition is a
  business/legal decision (which license, and whether it interacts with
  the still-unresolved BirdNET commercial-adjacent-distribution question
  recorded in `release-execution-state.md` §2) that this bounded
  engineering milestone cannot correctly resolve on its own -- exactly the
  case the governing task's own conditional ("only if... their disposition
  can be correctly resolved within this bounded milestone") anticipated.
  Left explicitly open; see "Limitations," below.
- **Host↔Camera Node `service_version` compatibility gate.** Confirmed
  display-only today, with no numeric compatibility floor enforced. This
  is a deliberate, already-documented choice (`ProductHealthStatus`'s own
  docstring: *"Deliberately excluded: a live Camera Node API version
  re-check, which would require a fresh network probe"*), not an
  oversight -- and the compatibility facts that actually gate correctness
  (`api_version`, `transport_protocol_version`) are already hard-enforced.
  No real version-skew failure mode was found in evidence. Inventing a
  numeric minimum-supported-version policy with no real semver contract
  behind it (this product is pre-1.0) would be manufactured complexity,
  not a fix for a demonstrated gap.
- **`scripts/deploy_windows_dev.py`.** Confirmed developer tooling only
  (explicitly out of scope for "the product installer" per
  `docs/roadmap.md` Phase 4 and this milestone's own non-goals). It
  already reuses `build_local_product.py`'s real functions rather than
  duplicating them, already has real rollback/retained-releases/userdata-
  preservation behavior for its *own* dev-loop purpose, and was used
  unmodified as this milestone's own native-Windows deployment mechanism
  (see "Native-Windows acceptance," below) -- not extended or changed.

## Implementation contract

**Pre-migration safety backup.** `initialize_database` (`storage/
database.py`) gained an optional `pre_migration_hook: (from_version,
to_version) -> backup_id | None`, called at most once per process start --
only when a pre-existing (not brand-new) database is genuinely about to
migrate forward, before either migration branch runs. `ProductRepository`
supplies `self._create_pre_migration_safety_backup`, a bound method that
constructs a `LocalBackupManager` from the repository's own already-
resolved `db_url`/`media_root` and calls `create_backup(kind="pre_
migration")` -- reusing the exact existing, already-verified backup
mechanism and the exact `kind`-value extension point
`appliance-storage-privacy-recovery-v1-contract.md` had already predicted.
If the backup itself fails for any reason, the exception propagates
unmodified and migration never runs -- fail before destructive mutation,
never after. `kind="pre_migration"` was added to every place `kind` was a
closed enumeration: `LocalBackupManager.create_backup`'s and its manifest-
reader's allow-lists, the `LocalBackupKind` Pydantic enum, the frontend
`LocalBackupKind` TypeScript type, and `LocalDataPage.tsx`'s label
("Before update"). `tests/conftest.py`'s repo-wide autouse isolation
fixture was extended (plain `os.environ` get/set/restore, not
`monkeypatch.setenv` -- see "Validation commands/results" for why) so
`LocalBackupManager`'s own default `backup_root` -- a relative path,
correct once a packaged launch has `os.chdir()`d into its runtime home,
dangerous resolved against a bare test run's cwd -- can never resolve to
this checkout's own real `data/backups/` during any test that does not
explicitly configure one itself.

**Real migration-chain-completeness check moved before the backup
attempt.** `_validate_or_migrate_schema_version` now calls the existing
`database_schema_version_is_compatible` (already used by the backup layer
itself) *before* firing the pre-migration hook -- a database with no
complete registered migration path to current is rejected immediately,
the same fact `_run_schema_migration_loop` would otherwise discover
mid-chain, but without first attempting a doomed backup of a database
`LocalBackupManager` could not have safely archived either.

**Genuine post-migration health check.** When (and only when) a real
migration actually ran this startup, `initialize_database` re-runs the
same `PRAGMA quick_check` integrity check the pre-migration snapshot
already used, and its result -- not the pre-migration one -- is what gets
reported and gates whether the process is ever considered ready. A failed
post-migration check raises before the app ever serves a request, even
though the migration's own SQL transaction genuinely committed. An
ordinary already-current launch still runs the check exactly once, same
cost as before.

**Honest surfacing of "a migration just happened."** `DatabaseSchemaStatus`
gained `migrated_from_version`/`pre_migration_backup_id` (both `None`
except on a real migration this process performed). Threaded through:
`RuntimePreflight` (`runtime.py`) and its console message (`--check`/a
real launch now says *"data format upgraded 52 -> 53 (safety backup
<id>)..."* instead of the ordinary message, when applicable); and
`ProductHealthStatus` (`api/schemas.py`/`api/main.py`), which gained
`database_migrated_from_version` -- surfaced as a one-time notice panel on
the Dashboard (`ProductHealthPanel.tsx`), the surface a normal user
actually sees, since the packaged Windows launcher has no console at all.

**Version single-source-of-truth.** `mockingbird.__version__` now resolves
from real installed package metadata (`importlib.metadata.version
("mockingbird")`, which resolves correctly for both an editable dev
install and a real packaged release wheel) with a clearly-named dev-
checkout-only fallback constant (`_DEV_CHECKOUT_FALLBACK_VERSION`),
mirroring `mockingbird_node.__version__`'s own already-existing,
already-accepted convention exactly rather than inventing a new one. The
FastAPI `app`'s decorative `version=` now reads `APP_VERSION` (already
imported) instead of an independent hardcoded literal. A new regression
test (`tests/test_version_provenance.py`) cross-checks `pyproject.toml`'s
version against both dev-checkout fallbacks and confirms the FastAPI app's
version matches the resolved `__version__` at runtime.

**Manifest provenance parity.** `BuildIdentity` gained `source_clean: bool`
(`not allow_dirty_source` at the one call site that constructs it),
mirroring the Camera Node build script's own existing convention. A new
independent verifier, `scripts/verify_release_artifact.py`, re-derives
every checkable fact about a built artifact from the files on disk
(recomputes `zip_sha256`, checks every `SHA256SUMS` entry, and -- unless
`--allow-dirty-source` explicitly accepts it -- requires `build_identity.
source_clean is True` and a `git:`-prefixed `source_state`) without
importing the builder's own code, so a bug in the builder's own
hashing/writing logic cannot also be invisible to its own verifier.

**CI.** `.github/workflows/ci.yml` (new -- none existed before): three
jobs -- `backend-tests` (Core gate, plus an isolated `python -m mockingbird
--check`), `frontend` (`npm ci && npm run build`, which already runs
`tsc --noEmit` first), and `packaging-smoke` (a real structural
`build_local_product.py` run with `--skip-gpu-runtime --skip-bioclip-
runtime`, since no local model bundle/offline wheel cache exists on a CI
runner, followed by `verify_release_artifact.py` against the result).
Scoped deliberately to what a Linux runner can honestly prove -- mirrors
`docs/local-product-packaging-design.md`'s own "fidelity-booted proxy"
framing for its own validation tier. Never claims to substitute for real
native-Windows acceptance.

**Documentation.** `docs/using-mockingbird.md` gained an "Upgrading
MockingBird" section (download, close, unpack over/alongside the old
folder, relaunch -- userdata is untouched by construction; the automatic
safety backup and how to confirm it worked; restoring it if something
looks wrong) and a short ffmpeg-dependency honesty note in "Add a camera."
`docs/appliance-storage-privacy-recovery-v1-contract.md` gained a "Closed
by Release Engineering Foundation v1" note directly under the section that
had deferred this work, so that design doc stops reading as an open gap.
New `SECURITY.md` (supported versions, GitHub private-vulnerability-
reporting as the primary channel -- no personal contact information
required or exposed -- in/out of scope, and an honest no-SLA-yet
expectation-setting note).

## Files changed

Two commits: `a56081a` (the milestone's own implementation) and `248853a`
(the real packaging-drift defect found by this milestone's own native-
Windows validation, fixed and regression-tested separately -- see gap 9
and "Native-Windows acceptance"). Combined diff, `64f787c..HEAD`:

```
 .github/workflows/ci.yml                                | 115 ++ (new)
 SECURITY.md                                              |  70 ++ (new)
 docs/appliance-storage-privacy-recovery-v1-contract.md   |  14 +
 docs/using-mockingbird.md                                |  39 ++
 scripts/build_local_product.py                           |  31 +-
 scripts/verify_release_artifact.py                       | 186 ++ (new)
 src/mockingbird/__init__.py                               |  28 +-
 src/mockingbird/api/main.py                               |   3 +-
 src/mockingbird/api/schemas.py                            |   9 +
 src/mockingbird/diagnostics/doctor.py                     |   5 +-
 src/mockingbird/repository/product_repository.py          |  31 +-
 src/mockingbird/runtime.py                                |  16 +
 src/mockingbird/storage/backup.py                         |   4 +-
 src/mockingbird/storage/database.py                       |  90 +-
 tests/conftest.py                                         |  51 +
 tests/test_local_product_packaging.py                     |  71 +-
 tests/test_persistence.py                                 | 235 ++
 tests/test_single_app_runtime.py                          |  41 +
 tests/test_verify_release_artifact.py                     | 231 ++ (new)
 tests/test_version_provenance.py                          |  58 ++ (new)
 web/src/api/types.ts                                      |   5 +-
 web/src/components/ProductHealthPanel.tsx                  |   9 +
 web/src/pages/LocalDataPage.tsx                            |   6 +-
 docs/release-engineering-foundation-v1-report.md          | this report
 24 files changed (excluding this report), 1327 insertions(+), 21 deletions(-)
```

The seven pre-existing, deliberately-preserved untracked superseded-
detector files were verified present and untouched before starting and
remain so (still untracked, byte-identical, per `git status`, re-verified
after both commits).

## Clean-install behavior

`initialize_database`'s brand-new-database branch (`recorded_version is
None`) never calls `pre_migration_hook` (nothing to preserve yet), verified
by a new dedicated test -- unaffected by this milestone's own feature work.
The existing "unpack -> double-click `Start MockingBird.vbs` -> guided
first-run setup" flow, `AppSetupStateModel` seeding, and the Windows
bundle's own dependency/model closure are otherwise unchanged, **except**
that the dependency closure was actively broken (see gap 9, above, and
"Native-Windows acceptance," below) for *every* launch -- clean-install
included, not only upgrade, since the missing `astral` import happens
during `product_repository.py`'s own module-level import chain regardless
of whether a database already exists. Fixed in the same commit
(`248853a`); a genuinely clean install would have failed identically to
the upgrade failure this milestone's own real deployment first surfaced.

## Upgrade behavior

Replace the app folder with a new version's unpacked bundle (userdata is
outside it, in `%LOCALAPPDATA%\MockingBird`, untouched by construction) and
relaunch. On the first launch that finds a pre-existing, older-but-
supported database: an automatic, verified `kind="pre_migration"` backup is
created and confirmed *before* any schema mutation; the full pending
migration chain then runs atomically (pre-existing behavior, confirmed
unchanged and still covered); a genuine post-migration integrity re-check
gates whether the app is ever considered ready; and the fact that this
happened is surfaced both in the startup console message and as a one-time
Dashboard notice pointing at the automatic backup in Local Data.

## Failure/interruption behavior

- **Backup itself fails** (disk full, unwritable, verification fails):
  migration never starts; the pre-existing database is untouched;
  regression-tested (`test_a_failed_pre_migration_backup_blocks_the_
  migration_entirely`).
- **Migration function raises mid-chain**: pre-existing, already-tested
  transactional-DDL guarantee (unchanged, re-verified green) -- the whole
  chain rolls back, not only the failing step.
- **Migration commits but the resulting database fails its own integrity
  check**: newly regression-tested
  (`test_a_post_migration_integrity_failure_blocks_the_upgrade_from_
  completing`) -- the process never reports readiness; the automatic
  pre-migration backup is the recovery path.
- **A database with no complete registered migration chain to current**
  (an unsupported-old or synthetic version): rejected immediately, before
  any backup attempt, with the same message as before
  (`test_database_needing_unknown_migration_is_rejected`, unchanged and
  still green).
- **Process killed mid-restore-from-backup** (a different but related
  operation): pre-existing, already-implemented sentinel
  (`detect_interrupted_restore`) -- out of this milestone's scope to
  re-verify beyond confirming it is unaffected (its own test file passed
  unmodified).

## Rollback/recovery semantics

There is no schema down-migration, and this milestone does not invent one
-- SQLite has no cheap down-migration story in this codebase, a fact the
deferred design review already recorded honestly. **Restoring the
automatic pre-migration backup is the documented, only real rollback
path**, exactly as that review anticipated, using the existing, already-
verified, already-atomic restore mechanism (its own automatic pre-restore
safety snapshot, staged/verified swap, and rollback-on-failure are
unchanged by this milestone). This is a verified backup/restore path, not
a claimed atomic in-place rollback -- consistent with the engineering
contract's "do not claim rollback where the implementation cannot actually
guarantee it."

## Model/dependency/license packaging behavior

MDv5 ONNX and BioCLIP-2 model bundles are still SHA-256-verified against
accepted hashes, never downloaded or committed; the BirdNET non-commercial-
license redistribution guard still runs at build time (exercised
structurally by the new CI packaging-smoke job on every change, where it
previously ran only on a manual local build) -- unchanged, re-confirmed,
not reopened. FFmpeg's non-bundling is now honestly documented rather than
silently discovered (see "Investigated, found not to need a code change,"
above). **Actively fixed**: the core Python dependency closure itself was
incomplete (`astral` missing -- gap 9, above); every core dependency is now
covered and a regression test prevents silent recurrence for any future
one.

## Host ↔ Camera Node compatibility behavior

Unchanged: wire-protocol versions (`api_version`, `transport_protocol_
version`) remain hard-gated; the Node's own reported `service_version`
remains an honest, display-only fact with no numeric compatibility floor,
a deliberate and still-reasonable choice given no real version-skew
failure mode exists in evidence for this pre-1.0 product.

## Native-Windows acceptance

**Directly validated on native Windows**, via this sandbox's real
WSL→Windows interop (`powershell.exe` reaching a real Windows-side Python
and a real passed-through NVIDIA GPU -- live-reconfirmed this session
before relying on it) and `scripts/deploy_windows_dev.py` (this project's
own established, previously-proven real-deployment mechanism -- reused
unmodified, not built by this milestone):

- **A real end-to-end deploy of this milestone's own committed HEAD**
  (`248853a`) to the shared Windows dev instance: real `npm ci`/frontend
  build, real win_amd64/cp312 dependency resolution (core + full GPU/CUDA
  + full BioCLIP tiers, not skipped), real embeddable-Python assembly, a
  real launch, and real post-launch verification -- **passed**, process
  healthy, BioCLIP reporting `available`.
- **A real, first-attempt-genuine defect found and fixed by this exact
  process**: the first deploy attempt crashed on launch --
  `ModuleNotFoundError: No module named 'astral'` -- a real packaging-
  dependency-closure gap unrelated to this milestone's own feature work
  (see "Repository findings" and the `248853a` commit). Root-caused, fixed,
  regression-tested, and the redeploy confirmed the fix for real. This is
  itself direct evidence the release path is now more trustworthy than
  before this milestone started, not merely unchanged.
- **The pre-migration safety backup + migration mechanism, proven by a
  completely organic real-world scenario stronger than any synthetic test
  this milestone could have constructed**: the shared dev instance's own
  real, pre-existing database happened to still be at schema **v35** (18
  versions behind current). This deploy's launch -- the exact same
  "replace the app, relaunch" path a real user's upgrade takes -- triggered
  a real, automatic, verified `kind="pre_migration"` backup (confirmed
  directly by reading that real `.mbbackup` archive's own `manifest.json`:
  `"kind": "pre_migration"`, `"database": {"schema_version": 35, ...}`,
  831,659,474 real bytes including real accumulated media), then migrated
  the live database to v53, then passed its own new post-migration
  integrity re-check, then started serving. Confirmed via real HTTP
  (`Invoke-WebRequest` through the same interop):
  `GET /api/product/health` returned `"ready": true`,
  `"database_schema_version": 53`, `"database_migrated_from_version": 35`,
  and `"backup": {"has_backup": true, "last_backup_verified": true, ...}`
  with a timestamp matching the archive exactly.
- **Version-provenance fix confirmed for real**: `GET /api/product/instance`
  returned `"git_commit": "248853a0f06f01b4f8b18943c278fc1b8e7aec9f"`
  (exactly this milestone's own real commit) and `"app_version": "0.1.0"`,
  resolved via `mockingbird.__version__`'s new `importlib.metadata` path
  against the real installed package inside the real deployed bundle --
  not merely unit-tested.
- Given the strength and organic realism of the migration evidence above,
  the smaller synthetic isolated-directory check originally planned
  (rewind-by-one-version against a throwaway database) was not additionally
  run -- it would have proven strictly less than what the real shared
  instance's own genuine 18-version gap already did.

**Structurally validated, hardware/OS-unverified in this pass**: the
`build_local_product.py --skip-gpu-runtime --skip-bioclip-runtime`
structural path `.github/workflows/ci.yml` actually runs (a real,
non-trivial cross-platform build executed directly on this Linux host,
followed by independent verification via `scripts/verify_release_
artifact.py`) -- this proves the packaging mechanism stays correct without
GPU/BioCLIP hardware available, which the real deployment above already
separately proved *with* them; between the two, both configurations are
now covered.

**Unsupported / deferred:** the literal double-click `Start MockingBird.vbs`
experience (as opposed to `deploy_windows_dev.py`'s own equivalent
programmatic launch of the same real packaged entry point) and real
physical mid-session ffmpeg-dependent camera-type acceptance (RTSP/USB/
DirectShow) were not additionally exercised this milestone -- the latter is
out of scope (this milestone is about the release/upgrade path, not camera
acquisition, a separately-accepted lane).

## Validation commands/results

Tier 1 (focused, per component):

- `pytest tests/test_persistence.py -q` -- **32 passed** (includes 6 new
  tests for the pre-migration backup and post-migration integrity-check
  mechanisms; zero regressions across the full pre-existing migration
  suite).
- `pytest tests/test_version_provenance.py -q` -- **4 passed**.
- `pytest tests/test_verify_release_artifact.py -q` -- **13 passed**.
- `pytest tests/test_single_app_runtime.py -q` -- **20 passed** (includes
  2 new `_print_preflight` message tests).
- `pytest tests/test_doctor.py -q -k ffmpeg` -- **4 passed**.
- `pytest tests/test_local_product_packaging.py -q -k "build_identity or
  manifest_records or dirty_source"` -- **13 passed** (includes new
  `source_clean` assertions on both the clean and dirty build paths).

Tier 2 (affected subsystem):

- A real, non-mocked structural run of `scripts/build_local_product.py
  --skip-gpu-runtime --skip-bioclip-runtime` on this Linux build host --
  first attempt correctly *refused* against this milestone's own
  in-progress uncommitted changes (`verify_clean_tracked_source` doing
  exactly its job); a second run with `--allow-dirty-source` (explicitly
  for this local-iteration check) completed the full pipeline end to end
  and `scripts/verify_release_artifact.py` confirmed the result.
- `python -m mockingbird --check` with an isolated `MOCKINGBIRD_HOME`
  (the exact invocation `.github/workflows/ci.yml`'s `backend-tests` job
  runs) -- passed, printed the ordinary (non-migrated) message correctly.

Tier 3 (Core gate -- this change touches `storage/database.py` and
`repository/product_repository.py`, both cross-cutting, so this was run):

- First full run: `python scripts/verify_core.py -q` -- 4631 passed, 2
  skipped, 23 deselected, 11 xfailed, **2 errors** (29m34s). The 2 errors
  were teardown-only `AttributeError`s in
  `tests/test_stream_playback_contract.py` (`get_live_camera_session_
  manager().stop_all(...)` called on a `types.SimpleNamespace`), a file
  this milestone never touched.
- **Root-caused, not merely dismissed as pre-existing.** `git stash`
  (tracked changes only -- the seven preserved files and this milestone's
  own new untracked files were never touched, confirmed via `git status`
  before and after) plus a second full Core run on that clean baseline
  reproduced **0** errors, proving one of this milestone's own tracked
  changes was a genuine contributing factor, not coincidence. Bisected with
  a fast, targeted 3-file reproduction (`test_camera_health.py`,
  `test_stream_monitoring_contract.py`, `test_stream_playback_contract.py`
  together, ~1-2 minutes per attempt instead of ~30) down to exactly
  `tests/conftest.py`'s own change: adding a `monkeypatch: pytest.
  MonkeyPatch` parameter to `_default_isolated_repository` (the autouse
  fixture present on literally every test in the suite, to isolate the new
  `MOCKINGBIRD_BACKUP_ROOT` default -- see "Pre-migration safety backup,"
  above) shifted pytest's per-test fixture-teardown order enough to expose
  a real, pre-existing, unrelated test-isolation fragility: `test_camera_
  health.py`/`test_stream_monitoring_contract.py` each manually save/
  restore `api_main._live_camera_session_manager` around a test rather
  than using `monkeypatch`'s own auto-revert, which is fragile to
  execution/teardown order by construction. **Fixed at the actual root**:
  `tests/conftest.py` now isolates `MOCKINGBIRD_BACKUP_ROOT` with plain
  `os.environ` get/set/restore in the fixture's own existing `finally`
  block instead of `monkeypatch.setenv` -- achieves the identical
  isolation goal (re-verified: `test_persistence.py`'s pre-migration-
  backup tests still pass, 34/34) without adding a new dependency to the
  shared fixture's own graph. The 3-file reproduction confirmed **0**
  errors after this fix, matching the clean baseline exactly. This is a
  genuine, narrow finding about pytest fixture-teardown ordering
  interacting with a pre-existing camera-session test pattern -- not a
  product defect, not a reason to believe `monkeypatch.setenv` is unsafe
  in general, and `test_camera_health.py`/`test_stream_monitoring_
  contract.py`'s own fragile manual-save/restore pattern was intentionally
  left as-is (out of this milestone's scope -- unrelated to release
  engineering) rather than also "fixed," since removing the proximate
  trigger already restores full test-suite health.
- Final full run with the fix applied: `python scripts/verify_core.py -q`
  -- **4633 passed, 2 skipped, 23 deselected, 11 xfailed, 0 errors, 0
  failures** (23m18s). Fully clean.

## Limitations explicitly still open

- **LICENSE remains genuinely absent.** A business/legal decision (which
  license; interaction with the still-unresolved BirdNET commercial-
  adjacent-distribution question in `release-execution-state.md` §2),
  correctly out of this bounded engineering milestone's authority to
  resolve unilaterally.
- **FFmpeg is not bundled.** Documented honestly (Doctor, using-
  mockingbird.md); full closure needs its own licensing-research pass,
  shaped like the already-completed BirdNET work, not a small packaging
  fix.
- **No literal hard-process-kill (SIGKILL) test exists for mid-migration
  crash recovery** -- the transactional-DDL guarantee is proven by a
  raised-exception test, not a real killed OS process; it rests on
  SQLite's own transactional durability rather than a test that induces
  an actual crash. Pre-existing limitation, not introduced or worsened by
  this milestone, and out of this milestone's own bounded scope to add.
- **`deploy_windows_dev.py`'s own `materialize_release` has no atomic
  staging** for its dev-loop release directories (found by a prior
  investigation agent, confirmed dev-tooling-only, explicitly out of
  Phase 4/this milestone's scope per `docs/roadmap.md`) -- not touched.
  Encountered directly, not merely theoretically, during this milestone's
  own native-Windows validation: an interop-layer failure (the documented,
  pre-existing `UtilAcceptVsock: accept4 failed 110` WSL↔Windows
  flakiness, unrelated to MockingBird) interrupted one deploy attempt
  after materialization but before its ledger entry was written. The
  tool's own existing refuse-on-mismatch check correctly declined to
  reuse or silently overwrite the resulting orphaned directory on retry
  ("already exists but does not match a ledger entry... refusing to
  overwrite"), requiring one manual `Remove-Item` before a clean retry
  succeeded -- exactly the manual-recovery experience this limitation
  already predicted, now confirmed real rather than only reasoned about.
- **CI cannot itself prove real-GPU/real-model/real-double-click
  behavior** on a Linux runner -- by design, honestly scoped, not a
  discovered gap to close later within this same lane.

## Decision

**A.**

An ordinary supported native-Windows user can, as of commit `248853a`:
obtain the artifact (`build_local_product.py`, structurally proven in CI
and directly in this milestone's own validation); reach a healthy Local
Only product from a clean state (clean-install path unaffected by this
milestone's own changes, and the one real defect that would have broken
*every* launch -- clean or upgrade -- is now fixed and regression-guarded);
preserve userdata through a supported upgrade (proven organically, for
real, across an 18-schema-version gap, with a verified automatic safety
backup); recover safely from an interrupted/failed upgrade (backup-failure
and post-migration-integrity-failure paths both fail closed, regression-
tested; the pre-existing transactional-DDL guarantee re-verified green);
and verify resulting health/version compatibility (real HTTP confirmation
of `app_version`/`git_commit`/`database_schema_version`/
`database_migrated_from_version` against the real deployed instance) --
without a developer checkout, WSL, manual migrations, or shell surgery
beyond the two ordinary product actions ("unpack and run" / "replace the
folder and relaunch").

This rests on more than structural/unit-test confidence: a real end-to-end
native-Windows deployment of this exact commit, a real defect found and
fixed by that same real deployment (not by static reading), and a real,
organically-occurring 18-version migration with a verified automatic
backup and passing post-migration health check -- confirmed via real HTTP
against the real running instance. The remaining gaps (LICENSE, full
ffmpeg bundling, the literal double-click launcher path as distinct from
`deploy_windows_dev.py`'s equivalent real launch, a literal SIGKILL
migration test) are explicitly recorded as open, bounded, and correctly
out of this milestone's authority or scope -- not silently absent.
