# Repository Consolidation & GitHub Synchronization v1 -- Report

**Status:** EXECUTED. Authorized directly by the owner. Repository/
documentation operations only -- no product code, schema, dependency,
hardware, deployment or CI change.

## 1. Starting and ending state

| | Start (verified 2026-09-26) | End |
| --- | --- | --- |
| Authoritative checkout | `/home/zkelder/projects/mockingbird-active` | same, and now the only development checkout |
| Branch | `main` | `main` |
| HEAD | `a9878a893175e067eefb75ec8155dd9bd79a8da9` | the reconciliation commit(s) recorded in §2, on top of `a9878a8` |
| Schema / version | `v61` / `0.1.0` | unchanged |
| Tracked changes | none | none |
| Untracked | the eight preserved files (§6) | the same eight, byte-identical |
| `origin/main` (fresh `ls-remote`) | `1772c36` -- an ancestor of HEAD, 451 commits behind | equal to local `main` (§2) |
| GitHub repository | `zkelder/mockingbird`, **private**, default branch `main`, viewer permission ADMIN; branch protection unavailable on this plan (HTTP 403), so no PR workflow is required | unchanged -- visibility not touched |
| Local `gh` auth | valid (`gho_` token, `repo`+`workflow` scopes); the earlier "invalid token" report was stale | unchanged |

Writer safety: one other Claude session (resumed 2026-09-25, cwd this
checkout) was present but idle -- no working-tree file modified in the three
hours before start; HEAD/index re-checked before every commit and before the
push. Nine orphaned `until ! pgrep -f ...; do sleep; done` wait-loops from
earlier sessions (parent `/init`) remain; each `pgrep -f` pattern matches its
own command line, so none can ever exit -- including one (pid `2339239`)
whose body would launch a Core run here. They were **not** killed (not this
session's processes); see §8.

## 2. Push

**Pre-push history review** of every blob introduced in `1772c36..a9878a8`
(3,322 new blobs, 956 paths; ~8.9 MB packed), not only the final tree. No
secret scanner is installed, so pattern checks were built with `git`/`grep`
and a second, independent pass re-ran the high-signal ones:

| Check | Result |
| --- | --- |
| Private keys, GitHub/AWS/Anthropic/Slack tokens | **none** |
| Password/token/URL-credential literals | all test fixtures (`hunter2`, `never-echo-node-credential`, fixture hosts / RFC 5737 addresses); two doc look-alikes are a credential *id* and a hash prefix |
| Databases, backups, support bundles, logs | **none** |
| Field media (images/video/audio) | **none**; only PWA icons and favicon |
| Large artifacts / model weights | **none**; largest blob is `product_repository.py` at 2.2 MB |
| BirdNET weights/labels | **none**; only adapter code and exclusion/notice text |
| Push-triggered automation | `.github/workflows/ci.yml` only -- tests, frontend build, structural packaging smoke; no secrets, no deploy/publish/release step |
| Preserved untracked files | 5 of 8 never committed. **3 were briefly tracked** (`3f6a49c`, removed index-only by `2549b32`: `small_bird_benchmark.py`, `wildlife.py.orig`, `test_small_bird_benchmark.py`), so their blobs ship in history -- ordinary superseded source, no sensitive content. Not removable without a history rewrite, which is out of scope |
| Personal information | `/home/zkelder`, `C:\Users\zachk` paths in ~49 docs/tests/scripts; the owner email once in a report (already the author email on every commit). Harmless for a private repository; a **pre-public** decision (§8) |

Verdict: no blocker for a private fast-forward push.

Push record: see §2a (filled in after the push).

## 3. CI

See §3a (filled in after the run).

## 4. Repository / worktree disposition

Integration was established by commit ancestry (`merge-base
--is-ancestor`) or by `git cherry` patch-equivalence (every commit `-`),
never by name or age. Retirement used non-forced `git worktree remove`,
`git branch -d` (ancestors) and `git branch -D` only where `git cherry`
reported zero unique patches. Everything retired is recoverable (§5).

| Item | State found | Disposition | Reason |
| --- | --- | --- | --- |
| `mockingbird-active` (`main`) | authoritative | **RETAINED** | the single development checkout |
| worktree `mockingbird-feature-replay` (`reconcile/windows-feature-stack`, `81f975c`) | 6 tracked modifications; 2 commits with no patch-equivalent in `main` ("Add per-zone monitoring policies", "Add safe storage retention controls") | **RETAINED** | dirty and unmerged; named stale by the Reconciliation v2 report but never documented as deliberately dropped -- owner decision (§8). Dirty diff also snapshotted |
| detached worktree `.../1d14ddf7-.../scratchpad/baseline` (`73dbcd4`) | 1 tracked modification, untracked benchmark script; inside another session's scratchpad | **RETAINED** | another session's material; dirty diff snapshotted |
| worktree `mockingbird-pending-feature-restore-v2` + branch `reconcile/pending-features-v2` | clean; both commits patch-equivalent | **RETIRED** | fully integrated |
| worktree `mockingbird-perception-replay-harness-v1` + branch | clean; ancestor of `main`; ignored `.venv` (346 MB), `data/perception_replay_fixtures/fixtures.json` | **RETIRED** | fully integrated; fixture archived first |
| worktree `mockingbird-place-intelligence-reporting-v1` + branch | clean; patch-equivalent | **RETIRED** | fully integrated |
| worktree `mockingbird-remote-transport-v1` + branch `remote-intermittent-wan-v1` | clean; ancestor; ignored `node_modules`/`dist` only | **RETIRED** | fully integrated |
| branches `feature/camera-node-connectivity-recovery-v1`, `feature/likely-sightings-evidence-fidelity-v1`, `feature/mockingbird-doctor-operational-health-v1`, `feature/multi-subject-visit-assembly-v1-phase1`, `integration/reconciled-feature-stack` | ancestors of `main` | **RETIRED** | fully integrated |
| branches `stage6-19-tracklet-visit-assembler`, `worktree-windows-dev-deploy` | one commit each, patch-equivalent | **RETIRED** | content already in `main` |
| branch `archive/stage6-18-failed-episode-boundary` | 1 unique commit | **RETAINED** (local only) | documented failed experiment (`tracklet-visit-assembly-contract.md`) |
| branch `preserve/native-automatic-identification` | 1 unique WIP commit | **RETAINED** (local only) | intentional preservation commit |
| branch `preserve/native-before-feature-reconciliation` | ancestor of `main` | **RETAINED** (local only) | intentional preservation name; costs nothing |
| independent clone `mockingbird-replay-independent-v2` | clean; every ref integrated or retained in `mockingbird-active` | **ARCHIVED, then removed** | full-directory tarball in recovery |
| independent clone `mockingbird` (`5010173`, 2026-07-07) | history integrated, but 7+ files of **uncommitted edits** with no other copy | **RETAINED** | dirty; diff snapshotted; owner decision (§8) |
| `mockingbird-reconciliation` (121 MB) | July 2026 repository-repair forensic workspace (bundles, fsck material, a stray `mockingbird.sqlite3`) | **RETAINED** | evidence store |
| `mockingbird-artifacts` (288 KB) | named Camera Node build artifacts | **RETAINED** | artifact store |
| `MockingBird` (empty), `birdcam` (empty dirs + venv symlinks only) | no files | **ARCHIVED, then removed** | pre-rename leftovers |

No remote branch or remote repository was deleted or created. Only `main`
was pushed; `archive/*`, `preserve/*` and `reconcile/*` remain local.

## 5. Recovery

Location: `/home/zkelder/mockingbird-recovery/2026-09-26-repo-consolidation/`
(mode `0700`, outside every retired directory).

| File | Content | Verified |
| --- | --- | --- |
| `mockingbird-active-all-refs.bundle` | every ref and worktree HEAD before cleanup | `git bundle verify` ok; restored into a scratch bare repo, all 19 refs identical to `refs-before.txt` |
| `refs-before.txt`, `worktrees-before.txt`, `stash-before.txt` | pre-cleanup ref/worktree/stash state (no stashes existed) | -- |
| `protected-untracked/protected-untracked.tar` + `protected-before.sha256` | byte copies of the eight preserved untracked files | extracted and `sha256sum -c` OK |
| `archives/mockingbird-replay-independent-v2.tar.gz` | the whole removed clone | `tar -t` ok |
| `archives/perception-replay-harness-v1-data.tar.gz` | the removed worktree's ignored `data/` | `tar -t` ok |
| `archives/MockingBird-and-birdcam-leftovers.tar.gz` | the two removed leftover directories | `tar -t` ok |
| `dirty-snapshots/*.diff` | tracked diffs of the three retained dirty checkouts | -- |

Restore a retired branch: `git fetch <bundle> 'refs/heads/<name>:refs/heads/<name>'`
from inside `mockingbird-active`; re-create its worktree with
`git worktree add ../<dir> <name>`. Restore a directory: `tar -xzf
archives/<file>.tar.gz -C /home/zkelder/projects`. Restore protected files:
`tar -xpf protected-untracked/protected-untracked.tar -C
/home/zkelder/projects/mockingbird-active`, then `sha256sum -c
protected-untracked/protected-before.sha256`.

## 6. Protected files

Before and after, SHA-256, all untracked, never staged:

```
63f9e5ba142069da49fcab1dc9ddb47eb29f95077389a5e72d123d75a68ef2e8  docs/wildlife-detector-training-contract.md.orig
81cdff0423f121128f52cbbda6f2670983f1480e87f513cf0e018c6cb86755dc  scripts/evaluate_small_bird_detector.py
ade97d9d46f446611518e3ea34723e0cecc1849dc5fc9510d1c7e5e4ea624d0a  scripts/materialize_wildlife_stage2.py.orig
a24aa6e294c04df113e17863942ad3710e95a7fac8c4756015fa858718a69f28  scripts/train_wildlife_stage2_rfdetr.py.orig
e85a2315fbe1487e545efd94da5b13b757ce8ef4d8b76c4dc1df4511075ded10  src/mockingbird/detectors/small_bird_benchmark.py
548f0706b5498b021289a28d2c6d1c375304b29b8f42bcc5bb40cf6875384b31  src/mockingbird/training/wildlife.py.orig
abad318b8df14c20f348d51ecd0946b3f47469b840142df361bd83bf51cc28b0  tests/test_small_bird_benchmark.py
f36f26ba9fffcbd8eab74ee9f66e149618f05aae9d35cf31e95cd90b468e273b  uv.lock
```

Full hashes: recovery `protected-untracked/protected-before.sha256`.
Post-operation re-verification: §2a.

## 7. Accepted-state documentation changes

- `docs/release-execution-state.md`: a new §3 entry recording the owner's
  sequencing-review acceptances (Native-Windows Field Reliability
  Corrections v1 at `83a0e86`; Today Truth Regression Repair v1 at
  `a9878a8`; Field Validation Closure v1 on cumulative evidence -- explicitly
  not a re-run) and superseding the stale "pending acceptance" / "remains
  unaccepted" statements, which are otherwise preserved; a §1 current-facts
  note (HEAD, schema, version, authoritative checkout, GitHub state); a
  header-log update; a §14 pointer to the current Core result
  (`6 failed, 6225 passed` -- not green). Authorization returns to **NONE**
  on closure; no next milestone written into it.
- `docs/today-truth-regression-repair-v1-report.md`,
  `docs/field-validation-closure-v1-report.md`: one acceptance line each.
- `CONTRIBUTING.md`: the "routinely many commits ahead of `origin/main` by
  design" statement, contradicted by this synchronization, reworded; the
  do-not-push-without-a-human rule is unchanged, and "never force-push" is
  added.

## 8. Owner decisions remaining

1. `mockingbird-feature-replay`: two never-integrated commits (per-zone
   monitoring policies, storage retention controls, July 2026) plus
   uncommitted edits. Keep, or explicitly abandon (recoverable either way).
2. `/home/zkelder/projects/mockingbird` clone: uncommitted July edits with no
   other copy (diff snapshotted). Keep, or delete.
3. Whether `archive/*` / `preserve/*` branches should ever be published.
4. Before any change to **public** visibility: the personal paths/email in
   docs and tests (§2), and that three superseded files live in history.
   Neither blocks the private synchronization done here.
5. The nine orphaned wait-loop shells (§1): they cannot fire, but killing
   them (`kill 1868935 1869542 1872144 1872420 1874310 192949 194209 2336862
   2339239` -- verify first) is the owner's call.
