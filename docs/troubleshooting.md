# Troubleshooting & Support

MockingBird is open-source software supported by its maintainer and
community on a best-effort basis. There is **no commercial support, SLA, or
hosted help desk**. This page is the entry point; the platform scope is in
[support-matrix.md](support-matrix.md).

## Step 1 -- check the in-app status

The Dashboard's **MockingBird status** area and each camera's **Needs
attention** note give a plain-language reason and next step. Camera health and
Observation health are reported separately, so you can tell which one has the
problem.

## Step 2 -- run Doctor

Doctor runs one bounded, read-only check of the database, storage, paired
Camera Node and the detector/species model setup.

- In the app: sign in as an Administrator and open **Doctor** from the menu.
- From a terminal (works even when the app will not start). On the Windows
  package, open a Command Prompt **in the unpacked folder**:

```bat
python\python.exe -m mockingbird doctor
```

From a source checkout use `python -m mockingbird doctor`. Add `--json` for
machine-readable output.

## Common problems

| Symptom | What it means / what to do |
|---|---|
| **Start observing says detection is unavailable** | Live detection needs a supported NVIDIA GPU and a current driver; there is deliberately no CPU mode. Update the NVIDIA driver. See [support-matrix.md](support-matrix.md#accelerators). Everything else still works. |
| **Species suggestions are unavailable** | The BioCLIP bundle is missing (a source checkout must supply it; the Windows ZIP includes it). Visits are still created; identify them yourself. Doctor names the missing piece. |
| **Camera "Needs attention" / unreachable** | Check address, credentials and power; for RTSP/USB/video import confirm `ffmpeg` is installed and on PATH (it is never bundled). `rtsps://` is refused by design. For a Camera Node, re-check its LAN address; if the device was replaced, see the Camera Node guide's reprovision section. |
| **"Waiting for capacity"** | Only two RTSP/USB/DirectShow Streams can be armed at once, and two live previews at once. Camera Node Streams are exempt. See [support-matrix.md](support-matrix.md#concurrency-limits-that-actually-apply-as-of-this-milestone). |
| **Windows SmartScreen warning** | The package is not code-signed. Verify its SHA-256, then **More info -> Run anyway**. |
| **"Did not shut down cleanly last time"** | Informational after a crash or forced stop; data is unaffected. Stop with **Local Data -> Shut Down MockingBird** next time. |
| **App will not start / database message** | MockingBird refuses to start rather than risk your data. Move `mockingbird.sqlite3` aside (do not delete) and restore a backup; steps in [using-mockingbird.md](using-mockingbird.md#if-something-goes-wrong). |
| **Update interrupted or something looks wrong after updating** | An automatic "Before update" backup exists in **Local Data**; restore it. |
| **Low or "not writable" storage** | Free space or fix folder permissions. Retention is off by default; **Settings -> Local Data** previews cleanup before anything moves to recoverable quarantine. |
| **Review/media files reported missing or unlinked** | `python\python.exe -m mockingbird storage-integrity` reports (read-only) media with no owning observation; quarantine/restore need an explicit `--yes`. |
| **Port 8000 in use** | MockingBird reports a port conflict instead of opening some other program; close the other program or the stale instance. |

## Backup, restore, replacement and recovery

- **Back up / restore:** Settings -> Local Data (verified backups; restore makes
  a safety backup first). See [using-mockingbird.md](using-mockingbird.md#backup-and-restore).
- **Replace the Host computer:** install MockingBird on the new computer, import
  your latest backup (`.mbbackup`) in Local Data and restore. Re-pair or
  re-check each camera's address; a paired Camera Node keeps working only
  against a Host it is paired with.
- **Replace a Camera Node:** reprovision the new device so it reattaches to the
  existing Stream rather than creating a duplicate; see
  [camera-node-install-guide.md](camera-node-install-guide.md) and
  [camera-node-reprovision-recovery-design.md](camera-node-reprovision-recovery-design.md).
- **Restart behaviour:** monitoring never silently starts after a restore;
  observation resumes only for Streams you armed.

## Gather a support bundle safely

```bat
python\python.exe -m mockingbird support-bundle --no-local-paths
```

The bundle excludes media, credentials and tokens but can still contain local
folder paths (including your Windows user name) inside Doctor's details. **Open
the `.zip` and read it before posting it in public.** Details in
[privacy-and-security.md](privacy-and-security.md#support-bundles).

## File a useful issue

Open an issue at <https://github.com/zkelder/mockingbird/issues> using the
**Bug report** form. Include: MockingBird version and build (Dashboard
status or `GET /api/product/instance`), Windows version and GPU/driver, camera
type, what you expected vs. saw, steps to reproduce, and the relevant Doctor
output. Search first, and **never paste passwords, pairing codes or full
unreviewed support bundles.** Feature requests for anything outside the 1.0
scope in the support matrix are welcome but not scheduled.

## Security problems

**Do not file a public issue.** Use private reporting as described in
[SECURITY.md](../SECURITY.md).
