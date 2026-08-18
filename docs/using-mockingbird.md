# Using MockingBird

This is the normal-user guide: install, start, first-run setup, add a
camera, start observing, review, and basic backup/recovery. It assumes
nothing about Python, servers, or the command line.

Setting up a development checkout, running the test suite, or working on
MockingBird's code is a separate audience -- see [README.md](../README.md)
and [AGENTS.md](../AGENTS.md).

## Install and start (Windows)

1. Unpack the `MockingBird-windows-x64.zip` folder anywhere you like --
   your Desktop, Documents, an external drive. Nothing outside that folder
   is needed.
2. Open the folder and double-click **Start MockingBird.vbs**.
3. Your browser opens to MockingBird automatically once it is ready. No
   window or terminal appears first.

That's it -- there is nothing to install first. The folder already contains
everything MockingBird needs to run.

To close MockingBird, close its browser tab. To fully stop it, use Task
Manager to end the "pythonw.exe" process, or simply shut down/restart your
computer -- MockingBird does not need to be manually stopped first, and your
data is safe either way.

## First-run setup

The first time you start MockingBird, it walks you through a short guided
setup instead of showing an empty screen:

1. **Welcome** -- a short explanation of what MockingBird does.
2. **Storage** -- where MockingBird keeps its data on this computer, how
   much space it is using, and whether that location is writable. MockingBird
   creates and manages this location itself; there is nothing to configure.
3. **Add a camera** -- choose the kind of camera you have, enter what it
   asks for, test the connection, and mark the part of the picture that
   matters (a feeder, a birdbath, a driveway). See "Add a camera" below for
   what each camera type needs.
4. **Start observing** -- once your camera is set up, you can start
   observing right away, or finish setup and start later from Cameras.

You can finish setup without adding a camera and add one later. This guided
setup only appears once; reopening MockingBird later goes straight to your
normal Dashboard, with everything exactly as you left it.

## Add a camera

From the Dashboard, choose **Add Camera**. MockingBird clearly marks each
camera type as available now, needing setup, or not supported yet -- it
never shows a placeholder option as if it already worked.

**MockingBird Camera Node** (a small companion program for a Raspberry Pi or
similar device with a camera attached):

1. On that device, start the Camera Node program. It prints a short-lived
   pairing code to that device's own screen.
2. In MockingBird, choose **MockingBird Camera Node**, enter that device's
   network address and the pairing code, then choose which camera view to
   use.
3. MockingBird shows a one-time preview so you can confirm you picked the
   right camera before saving anything.

Your Camera Node's pairing stays local to your network; MockingBird never
shows or asks for its underlying access credential directly -- pairing
handles that for you.

For a Camera Node that should keep running unattended and survive a
reboot, see the more technical
[Camera Node install guide](camera-node-install-guide.md) for installing
it as a supervised background service instead of starting it by hand each
time.

**A camera already connected to this computer** (USB, or your computer's
built-in camera): choose that option and MockingBird checks it directly.

**A camera or device with its own still-image web address**: enter that
address and MockingBird tests it before saving.

After choosing a camera, drag on the preview to mark the area that matters
(where birds actually land, for example) -- this helps MockingBird focus on
what you care about.

## Start observing

Open a camera from **Cameras** and use **Start observing** / **Stop
observing**. MockingBird shows plain camera health -- Healthy, Observing, or
Needs attention with a plain-language reason and what to do about it.
Observing only ever starts when you choose to start it; MockingBird does not
turn a camera on by itself.

MockingBird reports Camera health and Observation health separately: a
camera can be fully connected and ready while Observation itself needs
attention (for example, an unsupported graphics card), and vice versa -- you
always see which one actually has the problem. On a Windows PC with a
compatible NVIDIA graphics card and a current driver, Start observing needs
no extra setup; the pieces it needs are already included in your MockingBird
folder. If your PC's graphics card is not supported, MockingBird says so
directly instead of guessing or silently running in a reduced mode.

## Review

When MockingBird notices a meaningful wildlife visit, it appears in **Review
Queue** for you to confirm or correct. Nothing becomes part of your
confirmed history -- your Bird Log, your yard's statistics, or an export --
until you explicitly confirm or correct it. MockingBird's own guesses stay
labeled as guesses until then.

## Product status

The Dashboard shows a compact **MockingBird status** area: whether
MockingBird is ready or needs attention, storage space and writability,
cameras needing attention, how many cameras are currently observing, and
your most recent backup. An "Advanced diagnostics" section (closed by
default) has more technical detail if you ever need to describe a problem
precisely.

## Backup and restore

Open **Settings** (Local Data) to:

- **Create a backup** -- one file containing your cameras, Zones, reviewed
  history, and local media.
- **Download** a backup to keep a copy somewhere else.
- **Restore** a backup -- MockingBird automatically makes a safety backup of
  your current data first, and explains what will change, before you confirm.

Restoring is a two-step confirmation on purpose: it replaces your current
local data with the backup's.

## If something goes wrong

- **A camera shows "Needs attention"**: open that camera for a plain-language
  reason and the specific next step (for example, re-checking its address or
  re-pairing).
- **MockingBird did not shut down cleanly last time**: the status area says
  so after a crash or a forced shutdown; your data is unaffected; nothing
  further is needed.
- **Storage shows low space or "not writable"**: free up space, or check
  that the folder MockingBird uses is not read-only, then reopen MockingBird.
- **Logs**: MockingBird keeps its own log file inside its data folder (shown
  in Advanced diagnostics on the status area) if you ever need to share
  details for troubleshooting.

## Other supported hosts

Linux users with a development checkout can use `./start-mockingbird.sh`
(or `python -m mockingbird`) the same way Windows users use
`Start MockingBird.vbs` -- see [README.md](../README.md) for that developer
setup. The guided first-run experience above is identical on every host.
