# External Pre-Release Acceptance -- Private Cohort v1: Participant Materials

**Superseded 2026-09-29 for §§2-9 by
[gate-g-launch-package-v1/](gate-g-launch-package-v1/00-START-HERE.txt)**
(*Gate G -- Launch Package Refresh v1*; see
[its report](external-pre-release-acceptance-gate-g-launch-package-refresh-v1-report.md)).
The refreshed package targets candidate `2272126`. It corrects these
statements below, which no longer match that candidate: the four-step
onboarding (now five, with Account); stopping only via Task Manager (the
in-app **Shut Down MockingBird** is now preferred); BirdNET "downloads a
model the first time you use it" (it is never bundled or downloaded, and
is out of scope for the test); and `python -m mockingbird doctor` with no
packaged interpreter path. It also adds checksum verification, the
SmartScreen notice, and the support-bundle steps. §1 (the invitation
draft) is still usable. This document is kept unchanged below as history.

**Status: DRAFT MATERIALS ONLY -- NOT SENT, NOT APPROVED.** Prepared under
*External Pre-Release Acceptance -- Private Cohort v1* to satisfy that
milestone's §4 ("Participant materials"). Nothing in this document has been
sent to anyone. No participant is named, contacted, or assumed available.
Every bracketed `[...]` field is an explicit gap for the owner to fill in
at, or before, the approval checkpoint (`release-execution-state.md`
§3/§6.S) -- see the companion report's "Owner approval checkpoint" section
for the consolidated list.

All factual claims below (latency, recall, licensing, storage locations,
uninstall procedure, diversity targets) are drawn directly from already
-governed sources -- `docs/roadmap.md` ("Numeric release budgets," Gate G),
`docs/external-pre-release-acceptance-gate-g-plan-v1.md`, and
`docs/using-mockingbird.md` -- and restated for a non-developer participant
audience, not invented here. Where no governed number exists (onboarding
time, exit severity/count formula), this document says so explicitly rather
than inventing one, per the governing directive's own instruction.

Every material below keeps the product-doctrine truth boundary visible to a
participant: **Measured** (a direct sensor/algorithm reading, e.g. a
timestamp or a stored frame), **Inferred** (a model's informed guess, e.g. a
species suggestion, shown before any human confirms it), and **Reviewed**
(what a participant explicitly confirms or corrects -- the only truth that
becomes durable history). None of these materials promises guaranteed
species identification, a numeric latency SLA, a cloud dependency, or any
surveillance/security-alerting capability -- MockingBird is a private,
local-first nature observatory, not a security camera product.

---

## 1. Private invitation draft

> Subject: A private, very early look at something I've been building --
> MockingBird
>
> Hi [Name],
>
> I'm working on **MockingBird**, a local-first "nature observatory"
> application -- it watches a camera pointed at your yard, feeder, or
> birdbath, notices wildlife activity, and helps you review, correct, and
> build a history of what visits your place over time. Everything runs on
> your own Windows PC; there's no cloud account and nothing is uploaded
> anywhere by default.
>
> It isn't released yet, and this isn't a public beta -- I'm inviting a
> small, private group of people I trust (somewhere around 3-5 people) to
> actually install and use it on their own hardware before I finish it, so
> I can find real problems I can't find myself. If you have an actual bird
> feeder, birdbath, or yard with regular wildlife activity, a Windows PC,
> and some patience for an unfinished product, I'd love your help.
>
> What this involves, roughly:
>
> - Installing a private build (no installer, no admin rights, no Python --
>   unzip a folder and double-click a launcher) on your own Windows
>   computer.
> - Pointing a camera at some wildlife activity (your own camera, or a
>   Raspberry Pi Camera Node if you have or want one -- happy to help you
>   set that up).
> - Using the product for a while: reviewing what it captured, correcting
>   its guesses, and telling me what's confusing, broken, or genuinely
>   useful.
> - Sharing occasional, bounded diagnostic reports (never your raw camera
>   footage or database) when something goes wrong.
>
> Before anything is installed, I'll send you a short written explanation
> of what data stays on your machine, what (if anything) would ever leave
> it, and ask for your explicit written OK to proceed -- this is a real,
> if small, privacy commitment on your part (it's your camera, your
> property, potentially your household members walking past it), and I
> want you to go in with eyes open.
>
> No pressure at all if this isn't for you right now -- let me know either
> way.
>
> [Your name]
> [owner contact email -- placeholder, not yet designated]

**Not sent. Recipient, exact channel, and final wording require owner
approval** (see the companion report's approval checkpoint).

---

## 2. Written consent / participation agreement

> **MockingBird Private Pre-Release Testing -- Participant Agreement**
>
> **What this is.** MockingBird is unreleased software. You are testing a
> private, pre-release build, not a publicly released product and not a
> public beta. [Owner name] is the sole point of contact for support and
> for anything you report.
>
> **What MockingBird does with your data.**
>
> - MockingBird is **Local Only** by default: your camera footage,
>   database, and history stay on your own computer. No MockingBird
>   -operated cloud service exists.
> - Two features are optional and off by default, and would only ever
>   contact an outside service if you explicitly turn them on: (1) weather
>   context (Open-Meteo), and (2) bird-sound identification (BirdNET,
>   which -- if you enable it -- downloads a separately-licensed model the
>   first time you use it). Neither turns on the other.
> - Camera/RTSP login credentials you enter are stored **in plain text**
>   on your own computer (not encrypted) -- protected only by your normal
>   Windows account/file permissions, the same as any other local
>   application config file.
> - Privacy/Ignore Zones you draw exclude activity in that area from
>   triggering a Visit -- they do **not** guarantee every frame MockingBird
>   ever retains is pixel-redacted in that area. Please don't rely on a
>   Zone as a guaranteed blur/redaction if that matters to you.
> - Your camera may incidentally capture real images of people (household
>   members, visitors, delivery drivers) as well as wildlife. That footage
>   stays on your machine like everything else.
>
> **What I ask to collect from you, and what I don't.** By default, if you
> report a finding, I may ask for: a plain description of what happened;
> the built-in **Doctor** tool's summary or a **Support Bundle** export
> (both already exclude your camera passwords, pairing secrets, and media
> automatically); and basic facts about your setup (Windows/GPU, camera
> type, roughly how your cameras/network are arranged). I will **not** ask
> for your raw database file, raw camera images/video, or camera
> credentials as a routine part of reporting a finding. If reproducing a
> specific problem genuinely requires one specific piece of raw evidence,
> I will ask for that one thing, explain exactly why, and you're free to
> decline.
>
> **What this software does not promise.** MockingBird does not guarantee
> correct species identification -- it offers ranked, honest guesses for
> you to confirm or correct, and sometimes it will honestly say "bird,
> species uncertain" rather than guess. It does not promise a fixed time
> limit for how quickly a Visit appears (typically well under two minutes,
> occasionally longer during busy activity -- see the known-limitations
> document). It has no cloud dependency and no surveillance/security
> -alerting function -- it is a nature-observation tool, not a security
> product.
>
> **How long findings are kept.** Anything you report is kept at least
> through the end of this private testing process, so it can be used to
> fix real problems before any public release. You can ask me to delete
> anything you've submitted at any time.
>
> **Your right to withdraw.** You can stop participating at any time, for
> any reason, without needing to explain why. If you withdraw, your data
> stays exactly where it already was -- on your own computer, under your
> own control -- and I will delete anything you've sent me if you ask.
>
> **Acknowledgement.** By signing below, I confirm I understand and agree
> to the above:
>
> - [ ] I understand this is unreleased, private software, not a public
>   beta.
> - [ ] I understand MockingBird is Local Only by default and what that
>   means for my data.
> - [ ] I understand camera credentials I enter are stored in plain text
>   on my own computer.
> - [ ] I understand Privacy/Ignore Zones exclude triggers, not a
>   guaranteed pixel redaction of every retained frame.
> - [ ] I consent to sharing bounded diagnostic findings (Doctor summaries,
>   redacted support bundles, written descriptions) as described above.
> - [ ] I understand there is no guarantee of species-identification
>   accuracy, no numeric speed guarantee, no cloud dependency, and no
>   surveillance/security-alerting function.
> - [ ] I understand I can withdraw at any time without justification.
>
> Name: _______________________  Date: _______________
>
> Signature: ___________________________________________

**Proposed consent mechanism is explicit written opt-in** (per the private
-cohort operating decisions this milestone's own directive supplies, and
the already-proposed, not-yet-approved addendum in the Gate G plan). **Not
yet approved; not sent to anyone.**

---

## 3. Installation and system-requirement instructions

**Before you install anything:** please read and sign the consent
agreement above first.

**What you'll need:**

- A **Windows 10 or 11 PC (64-bit)**. This is the only fully supported,
  packaged installation path today.
- Automatic wildlife **detection** requires an **NVIDIA GPU that supports
  CUDA**. If your PC doesn't have one, MockingBird will still install and
  run, but it will honestly tell you detection needs setup rather than
  silently running slowly or incorrectly on CPU -- this is expected, not a
  bug, and please still let me know your setup either way, since that
  itself is useful information. Species identification and bird-sound
  identification (if you enable it) work fine without a GPU.
- A camera of some kind: your own IP camera, a USB/built-in Windows
  camera, or a Raspberry Pi if you'd like to try the dedicated Camera Node
  path (ask me if you want help setting one up).
- Some free disk space for the application, its models, and your growing
  history (a few GB to start).
- An actual outdoor space with real wildlife activity -- a feeder,
  birdbath, or similar. An empty yard won't give either of us much to look
  at.

**Installing:**

1. You'll receive a private download link and a checksum (`SHA256SUMS`)
   directly from [owner name] -- not a public download page.
2. Unzip the folder anywhere convenient (Desktop, Documents, wherever).
   There is no installer and nothing is written to the Windows registry.
3. Double-click `Start MockingBird.vbs` inside the unzipped folder. A
   browser window opens automatically.
4. That's it -- no Python, no command line, no administrator rights
   needed.

Continue to the first-run guide below once MockingBird opens.

---

## 4. First-run and first-use task guide

**The first-run wizard** walks you through four steps: **Welcome ->
Storage -> Add a camera -> Start observing.** Just follow it -- there's no
separate setup you need to do outside the app.

**What "it's working" looks like, in order:**

1. You see a live preview from your own camera. If your camera type isn't
   supported yet, MockingBird should tell you clearly why, rather than
   just failing silently -- if it doesn't, that's worth reporting.
2. After you start observing, real activity at your feeder/yard should
   eventually produce a **Visit** -- MockingBird's record of one piece of
   animal activity -- without you needing to do anything else.
3. You should be able to tell, just from the app itself, whether that
   Visit still needs your review or not.

**Where to look for activity:** check **Today** and **Bird Log** first --
that's the normal place new activity shows up, not the Review Queue.

**A note on timing, so you know what to expect:** based on real field
testing, it typically takes roughly **80 to 115 seconds** from real activity
happening to a Visit becoming visible, and it can occasionally take several
minutes longer during busy or crowded activity. That gap is normal
processing time (MockingBird waits briefly to make sure it has gathered a
complete picture of what happened before showing it to you) -- it is not a
freeze or a bug. If a Visit takes dramatically longer than that, or you
genuinely can't tell "nothing happened yet" apart from "still processing"
apart from "something's wrong," please tell me -- **this is one of the
specific things this private test exists to learn**, since no amount of
testing on my end can substitute for your own real patience and
expectations.

---

## 5. Correction / evidence-trust task guide

Please do this for at least a handful of real Visits during your testing:

1. Open **Review Queue** and look at a Visit MockingBird recorded.
2. Open its **evidence gallery** -- you should see every frame MockingBird
   captured for that Visit, not just one single picture.
3. MockingBird may offer a species guess. This guess is a **suggestion**,
   never a fact until you say so -- look for language like "likely" or
   "possible" rather than a flat, confident statement. Confirm it if it's
   right, correct it if it's wrong, or mark it however feels honest if
   you're not sure.
4. Sometimes MockingBird will honestly say something like "bird, species
   uncertain" instead of guessing. That is a **correct, expected
   behavior** -- not a failure you need to fix by picking something. An
   honest "I don't know" is better than a confident wrong guess.
5. **The one thing that matters most:** once you correct something, it
   should stay corrected. If you ever notice a correction you made
   reverting, disappearing, or being silently overridden by a new guess,
   **please report that immediately** -- of everything in this test, that
   specific kind of problem is treated as the most serious, because
   MockingBird's entire premise is that your explicit correction is the
   one thing that becomes durable, trustworthy history.

---

## 6. Backup, recovery, and uninstall instructions

**Backup (please try this at least once):** Settings -> Local Data ->
create a manual backup. Confirm the download actually completes and lands
somewhere on your computer.

**If something goes wrong (recovery):** close MockingBird, rename or move
`mockingbird.sqlite3` (in your local data folder) somewhere else, reopen
MockingBird, then restore from a backup via Settings -> Local Data. I'll
walk you through this live if you ever actually need it -- you shouldn't
need to do this proactively.

**If an update is provided during testing:** MockingBird automatically
backs itself up before applying any update that changes its internal data
format, and checks its own health afterward. You should see an on-screen
message telling you your data was updated. If you ever don't see that
message during an update, that's worth reporting.

**Uninstalling, when you're done testing (or any time):**

1. **Stop MockingBird first** -- close the browser tab, then end
   `pythonw.exe` in Task Manager (or just restart your computer). This
   step is required, not optional: Windows will refuse to delete the
   folder while MockingBird is still running.
2. **Delete the application folder** (the one with
   `Start MockingBird.vbs` in it). This removes MockingBird itself and
   **leaves your data untouched** -- if you ever unzip a fresh copy later,
   anywhere, it automatically reconnects to the same history.
3. **Only if you also want to permanently delete your data:** separately
   delete the `%LOCALAPPDATA%\MockingBird` folder. This is a **second,
   deliberate, irreversible step** -- it is never bundled with step 2, so
   you can remove the app without losing your history if you're not sure
   yet.

---

## 7. Known limitations and support boundaries

Please read this before you start -- knowing these in advance means you
won't mistake expected behavior for a bug:

- **No GPU, no automatic detection.** Detection requires an NVIDIA
  CUDA-capable GPU. Without one, MockingBird honestly reports a
  setup-required state for detection specifically -- species and
  bird-sound identification still work.
- **Typical delay is 80-115 seconds**, occasionally longer (several
  minutes) during busy activity, between real activity and a visible
  Visit. This is expected, disclosed behavior, not a bug.
- **During unusually busy, continuous multi-bird activity**, MockingBird
  may occasionally not create a separate Visit for every individual bird
  present. This is a known, disclosed limitation -- MockingBird
  deliberately prioritizes never falsely merging two different birds
  together over guaranteeing exactly one Visit per bird in that specific
  situation.
- **Camera/RTSP credentials are stored in plain text**, not encrypted, on
  your own computer.
- **Privacy/Ignore Zones** exclude triggers in that area -- they do not
  guarantee pixel redaction of every retained frame.
- **Bird-sound identification (BirdNET) is optional, off by default, and
  separately licensed** (non-commercial use) -- MockingBird never bundles
  it; enabling it downloads the model separately, with its own license
  notice shown at that point.
- **Not currently supported:** true multi-site (more than one physical
  "Place" per install), a native mobile app (browser/PWA works, but no
  app-store app), and remote/cellular/solar field deployment.
- **This is private testing, not finished software.** Rough edges,
  confusing moments, and real bugs are expected and exactly what this
  process is for.

**Support boundary:** [Owner name] is your only point of contact for this
test -- there's no separate support team. When something goes wrong, please
start with the built-in **Doctor** tool (`python -m mockingbird doctor`, or
the equivalent in-app diagnostics) and share its summary, or a **Support
Bundle** export, rather than trying to dig into internals yourself. Please
don't send raw database files, raw camera images/video, or camera
credentials unless I specifically ask for one and explain why.

---

## 8. Findings submission template

> **What did you do?**
> [describe the steps you took]
>
> **What did you expect to happen?**
>
> **What actually happened?**
>
> **How bad does this feel to you?** (crashed / lost data / very confusing
> / minor annoyance / just a suggestion)
>
> **Can you make it happen again?** (yes, reliably / yes, sometimes / no,
> only happened once)
>
> **Your setup:** Windows version + GPU (or "no dedicated GPU"); camera
> type (Camera Node/Pi, ONVIF, RTSP, USB/built-in, imported files);
> roughly how many cameras.
>
> **Doctor summary or Support Bundle**, if this seems like a real problem
> rather than a question (attach or paste; please don't include raw
> database/media unless asked).
>
> **Anything else?**

**Where to submit this:** **[private findings channel -- not yet
designated by the owner; see the companion report's approval checkpoint]**.
The Gate G plan's own §13 proposes reusing a private-repository issue
process or whatever mechanism the owner already uses for accepted-milestone
tracking, rather than building something new -- the specific channel itself
still needs the owner to pick it.

---

## 9. Participant withdrawal and data-handling instructions

- **You can withdraw at any time, for any reason, without needing to
  justify it.** Just tell [owner name] you're stopping.
- **Your MockingBird data never left your computer in the first place** --
  withdrawing doesn't change that. Local Only means your history, camera
  footage, and database stay exactly where they already were.
- **Anything you've already submitted as a finding** (descriptions,
  Doctor summaries, support bundles) is kept at least through the end of
  this private testing process, unless you ask for it to be deleted --
  just ask, at any time, including after you've withdrawn.
- **If you want to remove MockingBird and/or your data from your own
  computer**, see the uninstall instructions above (§6) -- removing the
  application preserves your data by default; a separate, explicit step
  permanently deletes it.

---

## Summary: what remains an explicit owner decision

Nothing above self-authorizes sending an invitation, collecting a
signature, or creating any account/channel. Per the governing directive's
§2 and the Gate G plan's own consolidated owner-decisions list, these
fields stay open until the owner approval checkpoint:

1. Exact participant identities and the specific recruitment channel used.
2. Final sign-off on the consent mechanism (explicit written opt-in is
   proposed above, matching the directive's own operating decision, but
   the exact form/wording is not yet approved).
3. The private findings-intake channel itself (a shape is proposed; the
   specific destination is not designated).
4. Any numeric onboarding-time or exit severity/count target beyond the
   qualitative criteria already governed in the Gate G plan -- none is
   invented here.
5. The actual go/no-go to send any invitation or begin recruitment.
