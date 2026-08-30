# Ongoing Monitoring Failure Diagnostics for RTSP / Local USB / Windows DShow v1

Closes Lane G's remaining implementation gap: once a non-Camera-Node Stream
(RTSP, local USB, Windows DirectShow) is armed and running, a concrete
failure cause (authentication, network, codec, decode) previously
collapsed to one generic ongoing-monitoring message, even though
setup-time validation already distinguished these causes. Camera Node is
out of scope and untouched.

## Starting state

Verified before any change (all matched the governing brief's stated
expectation exactly):

- **Branch:** `main`.
- **HEAD:** `b1c78dc` (Reconcile release-execution-state.md: accept Login
  Rate-Limiting & Authentication Abuse Resistance v1).
- **Schema:** `v58` (`CURRENT_DATABASE_SCHEMA_VERSION = 58`,
  `src/mockingbird/storage/database.py:45`) -- unchanged by this
  milestone; see "Validation," below, for why.
- **Latest accepted milestone:** Login Rate-Limiting & Authentication Abuse
  Resistance v1.
- **Lane G:** confirmed `PARTIAL, MATERIALLY CLOSED -- RELEASE-CRITICAL`
  in `docs/release-execution-state.md` §6.G, with this exact gap already
  named: "ongoing-monitoring failure-code collapse for non-Camera-Node
  providers... setup-time validation is unaffected and stays fully
  distinguishing."
- **Lane C:** `PARTIAL -- HIGH RELEASE VALUE` (§6.C, "Everyday Product /
  Discovery UX") -- a real closure pass (2026-08-22) already ran against
  it, leaving only bounded, enumerated, high-value-but-optional remaining
  items (Best Moments, calm daily summary, New/Regular presentation, etc.)
  -- none of them a detector-health/stale-message-precedence gap. No such
  gap was found or encountered during this milestone's own investigation,
  so §13's conditional "fix it only if literally the same shared
  precedence bug" clause never triggered; Lane C is untouched.
- **Gate A / Lane R:** confirmed `NOT DONE -- RELEASE-CRITICAL` (§6.R).
- **Authorization before this instruction:** confirmed `NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED` (§3).
- **Not pushed:** confirmed (`main` 250 commits ahead of `origin/main`,
  0 behind).
- **Worktree safety:** no active writer found (no `.git` lock files, no
  `MERGE_HEAD`/`REBASE_HEAD`, zero files modified in the preceding 10
  minutes, zero write-mode file descriptors from any other process into
  this worktree); several idle `ccd-cli` sessions share this machine but
  none held a lock or had touched the tree recently. The seven preserved
  untracked files were present and byte-identical (by size and mtime,
  `Aug 29 21:53`) at both the start and the end of this milestone.

## Reproducer

Direct code archaeology first established the exact mechanism (see
"Runtime architecture," below), then two independent RED proofs:

1. **Missing-capability RED**: the new test file
   (`tests/test_ongoing_monitoring_failure_diagnostics.py`) failed to
   collect at all (`ModuleNotFoundError: No module named
   'mockingbird.playback.stderr_drain'`) before any implementation
   existed.
2. **Behavioral RED, bisected against the real pre-fix code**: `git stash`
   of every file this milestone touches, then a standalone repro
   (`_LiveCameraSession._reader_loop()` driven directly, mirroring `tests/
   test_live_camera_session.py`'s own existing synchronous-call
   convention) pushed a real ffmpeg-shaped RTSP auth-failure stderr line
   (`"[rtsp @ 0x0] method DESCRIBE failed: 401 Unauthorized"`) through a
   real OS pipe before closing the fake process. Result against the
   genuine pre-fix code:

   ```
   status: failed
   last_error: Camera process ended before the session was stopped.
   has last_failure_code attr: False
   ```

   The specific evidence (`401 Unauthorized`) was silently discarded --
   the ongoing-monitoring path collapsed to the fully generic message
   regardless of cause, confirming the defect exactly as disclosed.
   `git stash pop` restored the implementation cleanly afterward (verified
   via `git status` and a re-run of the new test suite, both clean).

## Runtime architecture

Answering the ten governing questions (brief §6) from direct code reading:

1. **Which child processes are long-lived?** The MJPEG bridge process each
   of `rtsp_bridge.start_rtsp_mjpeg_process`/`local_camera_bridge.
   start_local_camera_mjpeg_process`/`windows_camera_bridge.
   start_windows_dshow_mjpeg_process` starts for a `_LiveCameraSession`
   (`playback/live_camera_session.py`) -- it runs for the Stream's entire
   monitored lifetime (up to `max_runtime_seconds`, default 30 minutes,
   then a fresh cycle), not a one-shot probe.
2. **Is stdout carrying media/frame data?** Yes -- `_reader_loop` reads
   raw MJPEG frame bytes from `process.stdout` continuously; this is the
   hot path and must never be slowed down.
3. **How is process lifetime supervised?** `DurableMonitoringSupervisor`
   (`monitoring/durable_supervisor.py`) reconciles desired vs. actual state
   once a second, starting/stopping via `_supervisor_start_camera`/
   `_supervisor_camera_status` (`api/main.py`), which wrap
   `LiveCameraSessionManager`. Each retry constructs a brand-new
   `_LiveCameraSession` (and, after this milestone, a brand-new drain) --
   never a reused one.
4. **Can stderr block independently?** Yes, structurally: before this
   milestone every long-running call site used `stderr=subprocess.DEVNULL`
   for RTSP/local USB/Windows DirectShow (unlike the bounded one-shot
   setup probe, `rtsp_bridge.probe_rtsp_stream`, which already opted into
   `stderr=PIPE` for exactly this reason). Switching to `PIPE` without a
   continuous reader would let stderr fill the OS pipe buffer and block
   the child indefinitely the moment it wrote enough error/warning text --
   a real ffmpeg deadlock risk, not hypothetical.
5. **What buffer growth is possible?** Unbounded, if naively captured --
   ffmpeg can run for the full 30-minute cycle emitting periodic warnings.
6. **What should happen if stderr is noisy for hours?** Keep draining
   forever, retain only a small bounded tail, never grow.
7. **How should the drain thread stop?** Only after the owning process is
   confirmed terminated (mirrors the existing `_stop_process`
   terminate-then-kill discipline) -- an EOF on the pipe is what lets a
   blocking `read()` return; the drain itself never tries to interrupt a
   still-open read.
8. **How should restart/retry interact with it?** Each retry is a fresh
   `_LiveCameraSession`/fresh process/fresh drain (see #3) -- no drain
   instance is ever reused across an attempt boundary.
9. **How is the most recent meaningful error retained?** A small,
   bounded, credential-redacted tail (4096 bytes, matching the existing
   setup-probe's own `_PROBE_MAX_STDERR_BYTES` bound), read fresh at the
   moment of failure.
10. **How is stale error text prevented from poisoning a later healthy
    state?** Two independent mechanisms, neither new: (a) each
    `_LiveCameraSession`/drain is fresh per attempt (#3/#8), so there is no
    carry-over within the in-memory session layer; (b) `ProductRepository.
    mark_monitoring_running` (the supervisor's own existing recovery path,
    `product_repository.py:15186`) already unconditionally clears
    `StreamRuntimeCheckpointModel.failure_code = None` the moment a Stream
    is confirmed healthy again -- provider-agnostic, untouched by this
    milestone, and directly re-verified still correct for the new codes
    (see "Retry/recovery," below).

Two hard chokepoints were found causing the actual collapse, both
independent of the missing stderr capture itself:

- `api/main.py`'s `_managed_camera_status` unconditionally discarded
  `failure_code` to `None` unless it was a literal member of
  `CAMERA_NODE_RUNTIME_FAILURE_CODES` -- so even a perfectly classified
  RTSP/local/Windows code would have been thrown away at this one
  conversion point.
- `product_repository.py`'s `mark_monitoring_backoff_with_failure_code`
  clamped any code outside that same Camera-Node-only set down to the
  generic `"camera_unavailable"` before ever reaching the database.

## Design

**Bounded continuous stderr drain** (`src/mockingbird/playback/
stderr_drain.py`, new): `BoundedStderrDrain` owns one dedicated daemon
thread per monitored process. The thread loops on a blocking
`stderr.read(4096)` -- zero CPU while idle, never a poll loop -- appending
each chunk to a `bytearray` capped at `max_retained_bytes` (4096, trimmed
from the front on every chunk so growth is never unbounded regardless of
how long or noisy the child is). `latest_text()` decodes and redacts the
*whole* retained tail in one pass (not per-chunk), so a credentialed URL
split across two read chunks is still caught by the redaction regex
reading the reassembled string. `.stop()` is a bounded, idempotent join
that assumes the caller already terminated the owning process (mirrors
`_stop_process`'s own terminate-then-kill contract) rather than trying to
interrupt a blocking read itself.

**One monitor lifecycle owns one drain lifecycle**
(`_LiveCameraSession`, `playback/live_camera_session.py`): the drain is
created in `__init__` alongside the process (`None` when
`process.stderr` is `None` -- Camera Node, or any fake without one),
started in `start()` alongside the reader thread, and stopped from every
exit path -- `stop()`, `pause()`, and a single `finally` wrapped around
`_reader_loop`'s entire body, which covers the clean-Stop early return, the
"process ended on its own" fallthrough, and the `except Exception` branch
with one line, so the drain thread can never outlive the reader thread
regardless of which path fires. `stop()`/`pause()` and the `finally`
race harmlessly -- the helper (`_stop_stderr_drain`) is idempotent.

**Classification, reusing the canonical vocabulary**: `_reader_loop`'s
failure branch now calls a new `_classify_ongoing_failure_locked()` helper
that dispatches on `self.playback_kind` to the same per-provider
`classify_*_failure_text` function setup-time validation already uses (or
a narrow new one for local USB/Windows DirectShow -- see below), passing
the drain's `latest_text()` and `frame_count > 0` (the ongoing-path
equivalent of the setup probe's `any_bytes_received`). The result is a
`(code, message)` pair: `code` is a new `last_failure_code` field (added
to `_LiveCameraSession`, `LiveCameraSessionSnapshot`, and threaded through
`_managed_camera_status`/`ManagedCameraStatus.failure_code`); `message` is
a calm, plain-language sentence for the existing, unchanged `last_error`
field (`StreamsPage.tsx`/`StreamDetailPage.tsx`'s "Last error:" text,
already required to be a safe sentence, never a raw code, by Pre-Freeze
Operability Gap Closure v1). Camera Node's own, separate, pre-existing
`safe_failure_code`-is-the-code convention is completely untouched --
checked first, unconditionally short-circuiting the new path.

**Plumbing widened, not duplicated**: `_managed_camera_status` now checks
the new `last_failure_code` field first, falling back to the original
Camera-Node-only check unchanged. `mark_monitoring_backoff_with_failure_
code`'s allowlist became `_ONGOING_MONITORING_APPROVED_FAILURE_CODES`
(`CAMERA_NODE_RUNTIME_FAILURE_CODES | {"fresh_frame_stale"} | RTSP_
ONGOING_FAILURE_CODES | LOCAL_USB_ONGOING_FAILURE_CODES | WINDOWS_DSHOW_
ONGOING_FAILURE_CODES`) instead of clamping every non-Camera-Node code to
`"camera_unavailable"`. `mark_monitoring_blocked` needed no change -- it
already stored whatever bounded code it was given; only the one function
that discarded them needed widening. Two advanced-tier message
dictionaries (`_camera_health_reason`'s single map, feeding
`CameraHealthSummary.failure_reason`; three inline per-state maps inside
`_camera_health_summary_from_models`, feeding `.message`) each gained ten
new entries -- one per new code, reusing the existing repeated-per-state
pattern rather than restructuring it.

## RTSP result

Reuses `classify_rtsp_failure_text` (renamed from the private
`_classify_probe_failure` -- zero other call sites existed anywhere in the
repository, confirmed by grep before renaming) verbatim, unmodified, for
both setup validation and ongoing monitoring -- the same concrete
underlying failure maps to the same product code either way, satisfying
the "no drifting second vocabulary" requirement structurally rather than
by convention. Five codes, all pre-existing:
`camera_setup_rtsp_authentication_failed`, `camera_setup_rtsp_unreachable`,
`camera_setup_rtsp_unsupported_codec`, `camera_setup_rtsp_negotiation_
failed` (also the honest no-evidence fallback, matching setup-time's own
calibrated default), `camera_setup_rtsp_decode_failed`.

**Live, real, end-to-end proof** (no mocking anywhere in the call chain):
a genuine `LiveCameraSessionManager().start()` against
`rtsp://127.0.0.1:1/...` (nothing listens there -- a real, disposable,
instantly-refused TCP connection, never touching any operator hardware).
Real ffmpeg subprocess, real `capture_stderr=True`, real
`BoundedStderrDrain` thread, real classification, zero fakes:

```
final status: failed
last_error: This camera's RTSP stream could not be reached. Check its network connection.
last_failure_code: camera_setup_rtsp_unreachable
```

## local_usb result

No prior text-based classification existed for this provider at all --
`local_camera_status` is a purely static/config-time check (device path
regex, platform, ffmpeg-binary presence), never runtime process-failure
text. Real, deterministic evidence gathered against this project's own
Linux dev sandbox (real ffmpeg 6.1.1, `ffmpeg -f v4l2 -i <path>`, no
V4L2 hardware or kernel module available or needed for these three cases):

| Scenario | Real ffmpeg stderr | Verdict |
|---|---|---|
| `/dev/video99` (nonexistent) | `Cannot open video device ...: No such file or directory` | evidence-backed: `camera_monitoring_local_usb_device_missing` |
| Existing file, `chmod 000` | `Cannot open video device ...: Permission denied` | evidence-backed: `camera_monitoring_local_usb_permission_denied` |
| Existing regular file (not a V4L2 device) | `ioctl(VIDIOC_QUERYCAP): Inappropriate ioctl for device` | **not** claimed as a distinct category -- honestly falls to `camera_monitoring_local_usb_unavailable` |

Device-busy, unsupported-format, and a generic decode failure were *not*
attempted -- no real V4L2 hardware or loadable kernel module (e.g.
`v4l2loopback`) was available in this sandbox to reproduce them, and
inventing them without evidence would violate the milestone's own "no
false precision" bar. This limitation is stated directly in
`local_camera_bridge.py`'s own module-level comment, not only here.

## windows_dshow result

Real evidence gathered live against this project's own reference Windows
dev host (`sandbox-has-windows-gpu-interop` -- real
`powershell.exe`/`ffmpeg.exe` via WSL interop, smoke-tested working before
use), read-only, no camera opened, nothing mutated:

- `Get-Command ffmpeg` resolved a real system install:
  `ffmpeg version 8.1.2-full_build-www.gyan.dev`.
- `ffmpeg -f dshow -list_devices true -i dummy` (device enumeration,
  opens nothing): **zero video devices** on this host (two audio-only
  devices -- a Razer mic, a Focusrite audio interface -- confirming no
  camera hardware is physically attached here).
- `ffmpeg -f dshow -i video="DefinitelyNotARealCameraXYZ123"` (a
  guaranteed-nonexistent name): identical text both times --
  `Could not enumerate video devices (or none found).` /
  `Error opening input: I/O error`.

Because this host has zero video devices at all, the "no devices exist"
and "devices exist but the requested name matches none of them" cases
could not be distinguished from each other -- both produce the identical
text. One evidence-backed category only:
`camera_monitoring_windows_dshow_device_unavailable` (anchored on the
distinctive `"could not enumerate video devices"` phrase), with
`camera_monitoring_windows_dshow_unavailable` as the honest generic
fallback for busy/permission/unsupported-format/decode causes -- none
evidence-backed on this host, none invented. No Windows camera-driver
research campaign was performed beyond this one bounded, reproducible,
read-only probe.

## Secret safety

`BoundedStderrDrain.latest_text()` always redacts through the existing
`redact_credentials_in_text` before returning -- the drain never exposes
raw retained bytes any other way. The ongoing path is more conservative
than the setup-time probe: `RtspProbeResult.detail` (setup) does carry the
redacted text outward for an advanced diagnostic; the ongoing path never
surfaces `latest_text()` anywhere outside `_classify_ongoing_failure_
locked` itself -- only the bounded `code` (never raw text) reaches the
structured log (`log_error_event(..., code=classified_code)`), the
checkpoint DB row, or any API response. New regression test
(`test_rtsp_ongoing_failure_never_leaks_credentials`) drives a real stderr
line containing an unmistakable canary credential through the real drain
and reader loop and asserts it never appears in `last_error`,
`last_failure_code`, or any logged structured-log field.

## Retry/recovery

No retry/backoff timing logic was touched (`monitoring/durable_supervisor.
py` has zero diff). Verified end-to-end against a real `ProductRepository`
(real SQLite, no mocking): `mark_monitoring_backoff_with_failure_code`
with a new code (`camera_setup_rtsp_authentication_failed`) produces a
specific `failure_reason` (`"This camera rejected its login
credentials..."`); a subsequent `mark_monitoring_running` (the existing,
unmodified recovery path) clears `failure_reason` back to `None` and
`state` back to `healthy` -- the pre-existing generic clearing mechanism
correctly recognizes and clears the new codes without any change to it.

## Long-run stress

Deterministic, no wall-clock hours: a real `sys.executable -c` subprocess
writes ~4.02MB (20,000 lines x 201 bytes) to stderr with nothing draining
stdout. Proven: the drain keeps up (`bytes_seen` matches the full ~4MB,
not stalled) and completes within a bounded `wait(timeout=15)`; the
process exits `0` (never blocked on stderr); `latest_text()` stays
`<= 4096` bytes throughout. A second, separate test proves stderr volume
never blocks concurrent frame delivery on `stdout` (~2.7MB of stderr
flooded from a background thread while 20 real frames are simultaneously
pushed and consumed -- all 20 arrive well under a 5-second bound). A
third proves 10 repeated start/stop cycles leave the drain-thread count
back at its exact starting baseline (no accumulation).

## Multi-Stream isolation

All new state (`_stderr_drain`, `last_failure_code`, `last_error`) lives
on `_LiveCameraSession` instance attributes -- no module-level mutable
dict, no shared "last error" of any kind. Proven directly: three
independent sessions (Stream A: real auth-failure text; Stream B: healthy
start-then-clean-stop; Stream C: real network-refused text) each retain
their own, uncontaminated `last_failure_code`.

## Setup/ongoing consistency

A dedicated parametrized regression test feeds four representative
stderr strings through `classify_rtsp_failure_text` directly (the
setup-time call shape) and through a full `_LiveCameraSession._reader_
loop()` run (the ongoing call shape) and asserts the two codes are
identical for every one -- structurally guaranteed by both paths calling
the exact same function, not merely tested as a coincidence.

## Validation

**Tier 1** (`tests/test_ongoing_monitoring_failure_diagnostics.py`, new):
25 tests, all independently confirmed RED (either via a real
`ModuleNotFoundError` before implementation, or via the git-stash
bisection above) and GREEN after. Covers every item in the brief's own
test matrix: RTSP auth/network/codec/unknown-exit; stderr safety
(high-volume no-deadlock, bounded retention, safe shutdown, credential
redaction); retry/recovery; multi-Stream concurrency/isolation; local_usb
and windows_dshow evidence-backed-only classification; failure-code
plumbing through `ManagedCameraStatus`; setup/ongoing consistency; a
dedicated Camera-Node-unaffected regression; repeated-cycle thread-leak
and concurrent-throughput proofs.

**Tier 2** (the established camera/source/monitoring/health subsystem
suite this project's own prior Camera / Source milestone named, plus
`test_stream_playback_contract.py` -- the actual home of the bridge-level
`popen_factory` fakes this change's new `capture_stderr` parameter
interacts with -- and this milestone's own new file; 20 files total): 503
passed, 11 xfailed (matching this project's own standing xfail baseline),
**zero failed**. Two real, transient regressions were found and fixed
along the way: `test_rtsp_bridge_endpoint_streams_mocked_mjpeg_without_
creating_truth` and `test_windows_dshow_bridge_endpoint_streams_mocked_
mjpeg_without_creating_truth` (both in `test_stream_playback_contract.py`)
had fixed-signature `fake_start` doubles that did not accept the new
`capture_stderr` keyword this milestone adds to `start_rtsp_mjpeg_
process`/`start_windows_dshow_mjpeg_process` -- both fixed by widening the
two fakes' own signatures (`**kwargs`/an explicit `capture_stderr: bool =
False` parameter), a small, bounded, test-only fix, not a product defect.

`ruff check`: zero new findings on every touched/new file, each
individually confirmed via direct `git stash` clean-baseline bisection --
`product_repository.py` (57 pre-existing, byte-identical count before and
after), `api/main.py` (26 pre-existing, identical), `local_camera_bridge.
py` (1 pre-existing unrelated `F401`, identical), `test_stream_playback_
contract.py` (1 pre-existing unrelated import-placement finding,
identical); `stderr_drain.py`, `rtsp_bridge.py`, `windows_camera_bridge.
py`, `live_camera_session.py`, and the new test file are all fully clean.

**Tier 3** (`scripts/verify_core.py`, one full run, bare, no `slow`-marker
deselection beyond the script's own default -- launched only after Tier 1/2
were both clean, per the governing brief's own sequencing): **5310
passed, 3 skipped, 23 deselected, 11 xfailed, zero failed** (34m22s). No
bisection was needed -- unlike several recent milestones' own Tier 3 runs,
this one produced no failures of any kind, related or not.

## Hardware evidence

**Actually tested, real**: real ffmpeg 6.1.1 on this project's own Linux
dev sandbox (V4L2 error-text evidence, `local_usb`); real ffmpeg.exe 8.1.2
on the project's own reference Windows dev host via WSL interop
(DirectShow error-text evidence, `windows_dshow`, read-only device
enumeration + one guaranteed-nonexistent-name probe, no camera opened, no
production instance touched); one real, live, end-to-end RTSP-unreachable
proof through the completely real, unmodified product code path (real
`LiveCameraSessionManager`, real ffmpeg subprocess, real refused TCP
connection, zero mocking).

**Not tested, honestly disclosed**: no real RTSP camera was available to
produce a real auth/codec failure end-to-end (only the unreachable case
was practical without a disposable real or simulated RTSP server); no
real local USB or Windows-attached camera device was available for either
provider (this Windows dev host has zero video devices attached at all,
confirmed directly by real device enumeration) -- so device-busy,
permission-on-a-real-device, and unsupported-format could not be
attempted for either provider, and are not claimed. The operator's real
Camera Node and real long-lived `MockingBirdDev` deployment were never
touched, per the brief's own explicit instruction (Camera Node is out of
scope for this milestone in the first place).

## Remaining risks

- Real local USB / Windows DirectShow hardware acceptance (device-busy,
  permission-on-real-hardware, unsupported-format) remains genuinely
  untested -- honestly generic behavior for those cases by design, not a
  known defect, but not proven against real hardware either.
- A real RTSP camera's own auth/codec failure text was never observed
  live (only via the same fixture strings `test_rtsp_probe.py` already
  established as representative for setup validation) -- the *ongoing*
  path's real-process wiring was proven live (unreachable case); the
  *classification* function itself was already accepted, unchanged
  evidence from setup validation.
- The advanced-tier message dictionaries
  (`_camera_health_reason`/`_camera_health_summary_from_models`) now carry
  ten new entries each in three near-duplicate inline maps -- matches this
  function's own pre-existing repeated-per-state pattern rather than
  refactoring it (out of this milestone's bounded scope), so a future
  fourth state would need the same three-way duplication again.

## Lane G disposition

The disclosed remaining implementation gap -- ongoing-monitoring
failure-code collapse for non-Camera-Node providers -- is closed for RTSP
(fully, reusing the accepted setup-time vocabulary) and for local
USB/Windows DirectShow (to the honest limit real evidence supports,
explicitly not further). Lane G moves from `PARTIAL, MATERIALLY CLOSED`
to **MATERIALLY CLOSED / VALIDATION REMAINS** -- real local USB/Windows
camera hardware acceptance and a real RTSP camera's live auth/codec
failure remain outstanding, per "Remaining risks," above; this is not
claimed as full hardware validation.

## Decision

**Classification A.** Every listed acceptance-bar item is met with real
evidence: the ongoing generic-collapse defect was reproduced against the
real pre-fix code (git-stash bisected, not merely inferred); stderr is now
captured safely and continuously with a real high-volume stress proof of
no deadlock and bounded memory; credential redaction is proven by a
dedicated regression test; RTSP ongoing classification is actionable and
structurally identical to setup-time classification (reuses the same
function); recovery is proven to clear stale failure state end-to-end
against a real repository; multiple Streams are proven independent; Tier
1 (26/26), Tier 2 (503 passed/11 xfailed/0 failed across 20 files), and
Tier 3 (5310 passed/0 failed) are all clean. Local USB/Windows DirectShow
deliberately do not claim more precision than real evidence supports --
per the brief's own explicit exemption, this does not block Classification
A.
