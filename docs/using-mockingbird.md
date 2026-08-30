# Using MockingBird

This is the normal-user guide: install, start, first-run setup, add a
camera, start observing, review, and basic backup/recovery. It assumes
nothing about Python, servers, or the command line.

Setting up a development checkout, running the test suite, or working on
MockingBird's code is a separate audience -- see [README.md](../README.md)
and [AGENTS.md](../AGENTS.md).

## Platform & hardware support

This is an honest summary of what is actually validated today, not a
promise that every platform listed here has been tested the same way.

**Computer (Host)**

| Platform | Status |
|---|---|
| Windows 10/11 (64-bit) | **Supported and validated.** The packaged download above is built, tested, and released for this platform, including GPU-accelerated wildlife detection. This is MockingBird's primary, release-tested platform today. |
| Linux | Structurally supported for a development checkout (`./start-mockingbird.sh`), and MockingBird's own automated tests run continuously on Linux. There is no packaged "unpack and run" Linux download yet, and no dedicated Linux hardware acceptance has been performed. |
| macOS | Not yet verified, and not part of this release. Microphone-based bird-sound identification specifically is known not to work on macOS -- MockingBird says so plainly rather than failing silently. |

**Wildlife detection** (the part that notices something is there)

Live wildlife detection needs a computer with a supported **NVIDIA
graphics card**. There is deliberately no slower "CPU-only" mode for this
part: MockingBird would rather tell you plainly that detection isn't
available than quietly run a degraded version without saying so. If your
graphics card isn't supported, **Start observing** says so directly instead
of guessing (see "Start observing," below). Everything else -- reviewing
history, your Bird Log, importing recorded video, backup and restore, and
settings -- works the same with or without a supported graphics card.

**Species and sound identification** (the part that guesses what it is)

Species suggestions and bird-sound identification both run on any
computer's regular processor -- neither needs a graphics card. If either
isn't set up, or its runtime isn't available, wildlife Visits are still
created normally; you only lose the automatic guess until you identify it
yourself.

**Apple Silicon and AMD graphics cards:** not supported today. MockingBird
does not claim to work on them merely because the underlying open-source
libraries theoretically could -- no Apple or AMD hardware has been used to
test this product.

**MockingBird Camera Node:** the validated reference hardware is a
Raspberry Pi 4 with its camera attached, running Raspberry Pi OS. The
Camera Node software does not require a Raspberry Pi specifically -- a
similar Debian-based Linux device with a USB camera can run it too -- but
only the Raspberry Pi 4 path has actually been tested end to end (install,
reboot, upgrade, and recovery). A device without a Pi camera reports that
plainly instead of failing the whole install.

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

**A network camera** -- MockingBird can discover many ONVIF-compatible
cameras on your network and configure them automatically (host, port, and
username/password only); if yours isn't discoverable, enter its RTSP
address directly instead. A `rtsps://` (secure RTSP) address is honestly
refused with an explanation rather than silently treated as insecure
`rtsp://` -- MockingBird does not support verifying that kind of encrypted
connection yet.

**A camera already connected to this computer** (USB, or your computer's
built-in camera): choose that option and MockingBird checks it directly.

**A camera or device with its own still-image web address**: enter that
address and MockingBird tests it before saving.

**Recorded wildlife video or images you already have** -- no live camera
needed. Choose this option to create a place to import video/image files
into, then use **Import Media** (always in the main menu, not hidden away)
to add the files themselves and analyze them the same way a live camera's
activity is analyzed.

A MockingBird Camera Node needs nothing else installed -- everything it
needs is already in your MockingBird folder. A network camera, a USB or
built-in camera, and recorded video import each additionally need a free
program called **ffmpeg** installed on this computer and available on its
PATH; if it isn't there yet, MockingBird says so plainly (rather than
failing in a confusing way) and links to where to get it.

After choosing a live camera, drag on the preview to mark the area that
matters (where birds actually land, for example) -- this helps MockingBird
focus on what you care about.

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

## Use MockingBird on your phone

MockingBird's whole everyday loop -- Today, a Visit's evidence, review,
Bird Log, Place Story, camera health -- works on a phone's browser, not
just a desktop. On the same device MockingBird is running on, this needs
nothing extra. From a *different* device (your phone, on the same home
WiFi), MockingBird needs to be told to answer the network, not just this
one computer -- off by default, so nothing changes unless you ask for it:

1. Close MockingBird if it's running.
2. Start it with two extra words: on Windows, open Command Prompt in
   MockingBird's folder and run `"Start MockingBird.cmd" --host 0.0.0.0
   --allow-network` (a shortcut can be edited to add these to its Target);
   on Linux/macOS, `./start-mockingbird.sh --host 0.0.0.0 --allow-network`.
3. Open **Settings**, then **Connection & Remote Access**, for the exact
   address to open on your phone (also copyable from there).

Signing in is required either way -- enabling network access never skips
it. This device serves plain HTTP unless you separately add a reverse
proxy for TLS, so only do this on a WiFi you trust (see "Use MockingBird
away from home," next, for a securable path). Add MockingBird to your
phone's home screen (your browser's "Add to Home Screen"/"Install") for an
app-like icon -- MockingBird still needs a real connection to this device
for real data either way; installing it does not make it work offline.

## Use MockingBird away from home

The supported way to reach MockingBird when you're not on its home WiFi is
a private network between your phone and this device -- for example
[Tailscale](https://tailscale.com) or a similar WireGuard-based tool.
Install it on both this device and your phone, sign in to the same private
network on both, then open MockingBird at the private address that tool
gives this device (still starts with `--allow-network` as above; Settings
still shows the exact address to use).

MockingBird does not require, and does not itself provide, a cloud
account, a cloud relay, or a hosted service to do this -- your data and
this connection stay between your own devices. Forwarding this device's
port directly on your home router so it is reachable from the public
internet is **not supported** -- it would expose an unencrypted connection
to anyone, not just you.

## Product status

The Dashboard shows a compact **MockingBird status** area: whether
MockingBird is ready or needs attention, storage space and writability,
cameras needing attention, how many cameras are currently observing, and
your most recent backup. An "Advanced diagnostics" section (closed by
default) has more technical detail if you ever need to describe a problem
precisely.

## Deeper diagnostics

If something needs more than the Dashboard's own status area to describe,
two additional tools exist alongside MockingBird -- normally only needed
for a support conversation, not everyday use:

- **MockingBird Doctor** (`python -m mockingbird doctor` from a terminal in
  MockingBird's folder) runs one bounded check of your database, storage,
  paired Camera Node, and detector/species-identification setup, and prints
  a plain-language summary of anything that needs attention.
- **A support bundle** (`python -m mockingbird support-bundle`) writes one
  small file safe to share for support -- it never includes camera
  passwords, pairing secrets, or media, only Doctor's own check results, a
  recent (automatically redacted) slice of MockingBird's log, and version
  facts.

## Backup and restore

Open **Settings** (Local Data) to:

- **Create a backup** -- one file containing your cameras, Zones, reviewed
  history, and local media.
- **Download** a backup to keep a copy somewhere else.
- **Restore** a backup -- MockingBird automatically makes a safety backup of
  your current data first, and explains what will change, before you confirm.

Restoring is a two-step confirmation on purpose: it replaces your current
local data with the backup's.

## Upgrading MockingBird

1. Close MockingBird (close its browser tab; MockingBird itself does not
   need to be stopped first).
2. Download the new version's `MockingBird-windows-x64.zip` and unpack it
   -- anywhere, including over the old folder or as a fresh folder next to
   it. Your cameras, Zones, and reviewed history are **not** stored inside
   this folder, so replacing it changes nothing about your data.
3. Double-click **Start MockingBird.vbs** in the new folder, the same as
   any normal start.

That's it -- there is no separate installer or upgrade wizard. The first
time the new version opens your existing data, it may need to update its
internal data format to match; when it does, MockingBird automatically
creates a safety backup of your data first, before changing anything. You
don't need to do anything for this to happen, and you can still confirm it
happened afterward: the status area shows a short note ("MockingBird
updated your data on this start...") the first time you open it after an
upgrade that needed one, and that automatic backup appears in **Local
Data** alongside any backups you created yourself, labeled "Before
update."

If anything looks wrong after upgrading, restore that automatic backup
from **Local Data** exactly as described in "Backup and restore," above --
it returns your data to exactly how it was the moment before the update
ran.

Older MockingBird versions are not supported as an upgrade source forever;
if a very old version's data cannot be updated automatically, MockingBird
says so plainly rather than guessing, and the same "Backup and restore"
recovery path still applies.

## If something goes wrong

- **A camera shows "Needs attention"**: open that camera for a plain-language
  reason and the specific next step (for example, re-checking its address or
  re-pairing).
- **MockingBird did not shut down cleanly last time**: the status area says
  so after a crash or a forced shutdown; your data is unaffected; nothing
  further is needed.
- **MockingBird won't start, or shows a message about its local database**:
  MockingBird checks its database before opening and refuses to start
  rather than risk existing data if that check fails -- it never silently
  modifies or replaces a database it can't safely read. To recover:
  1. Close MockingBird if it's still running.
  2. In MockingBird's data folder (the same folder shown on the Storage
     step during first-run setup and on the Local Data page), move the
     `mockingbird.sqlite3` file somewhere else -- don't delete it, in case
     you want it looked at later.
  3. Reopen MockingBird. With no database file present it starts fresh, the
     same as a new install.
  4. Open **Local Data**, then **Import backup** to add your most recent
     `.mbbackup` file if it isn't already listed, and **Restore** it. This
     replaces the fresh, empty database with your backed-up data.

  This is why creating a backup before you need one matters -- see
  "Backup and restore," above.
- **Storage shows low space or "not writable"**: free up space, or check
  that the folder MockingBird uses is not read-only, then reopen MockingBird.
- **Logs**: MockingBird keeps its own log file inside its data folder (shown
  in Advanced diagnostics on the status area) if you ever need to share
  details for troubleshooting -- or use **a support bundle** (see "Deeper
  diagnostics," above) for one small file with the relevant pieces already
  gathered and redacted.

## Other supported hosts

Linux users with a development checkout can use `./start-mockingbird.sh`
(or `python -m mockingbird`) the same way Windows users use
`Start MockingBird.vbs` -- see [README.md](../README.md) for that developer
setup. The guided first-run experience above is identical on every host.
See "Platform & hardware support," near the top of this guide, for what is
and isn't validated on each one.
