# Camera Node Configuration Backup + Reprovision / Replacement Recovery v1

**Product flow improved:** a Camera Node is replaceable field infrastructure
-- an SD card dies, the OS gets reinstalled, the Pi or camera gets replaced,
or an operator deliberately factory-resets a node -- and MockingBird's Place
history, Observations, reviewed truth, and historical analytics stay intact
on the host, with a bounded path to reattach new physical hardware to the
same logical camera instead of losing it or duplicating it.

**Why this is next:** named as still-open by the immediately prior milestone
("Camera Node Boot Identity + Autonomous Recovery v1") and by
[roadmap.md](roadmap.md)'s Gate D: "a configuration backup/export mechanism,
the replacement-node workflow itself..., and golden-Pi power-supply/
boot-media/networking guidance." A real credential re-pair through Guided
Camera Editing's repair flow was already live-proven for the *same* Node
identity; a genuine physical-device swap was not yet a deliberate capability
or acceptance case (see roadmap.md's field-failure acceptance matrix, item
12).

## 1. State inventory

### Host-authoritative state (survives node replacement automatically)

Place/Source/Stream identity, Zones, reviewed Observations (`ReviewLabel`),
Visit/Event history, monitoring policy, `CameraConfigurationRevision`
history, and export/analytics all live in the host's own SQLite database,
addressed by `CameraSourceModel.id`/`StreamModel.id` -- primary keys that
never change across a repair or a confirmed replacement. "Place" itself is
not a distinct row in this product (see [glossary.md](glossary.md)); it is
the whole local installation, matching the Personal/Home single-site profile
in [product-doctrine.md](product-doctrine.md).

### Node-local configuration (what actually needs restoring)

Two separate files on the Node device, neither containing a secret:

- `/etc/mockingbird-camera-node/node.env` -- display name, network bind,
  provider selection, camera/image bounds, pairing TTL, preview-viewer cap,
  log level. This is the portable "intent" this milestone backs up.
- `/var/lib/mockingbird-camera-node/pairing.json` -- `{version,
  credential_sha256}` only. Node-local, not portable, and not worth
  exporting: a hash with no matching credential on a different device is
  meaningless, and reprovisioning always requires fresh pairing regardless
  (see "Secrets," below).

### Hardware-derived state (must never be copied blindly)

`boot_id` (kernel-derived, changes every real reboot -- never a stable
identity), the Node's `node_id` (`sha256(display_name)` -- software-derived,
not hardware-derived, and already used as a compatibility guard, not an
identity claim), actual advertised camera capability (resolution, capture
profiles), and physical camera/device identity. None of these are exported;
all are re-discovered live from whatever physical hardware answers at
pairing/apply time.

## 2. Existing mechanism this milestone extends

Guided Camera Editing's Camera Node repair path (`docs/camera-node-pairing-
persistence-design.md`) already: re-pairs via the same one-time-code path as
first-run setup; durably persists the credential before it can be lost to a
refresh; previews impact before committing; applies atomically in one
DB transaction; and preserves Source/Stream/Zone/history untouched. It was,
however, gated on the Node's own `node_id` being unchanged
(`_camera_configuration_proposed_config`, `camera_node_identity_changed`) --
correct default behavior (a different Node answering is ordinarily a
mistake), but it structurally blocked a genuine, deliberate hardware
replacement. This milestone adds one explicit, operator-confirmed override
to that same guard rather than building a second replacement mechanism.

## 3. Configuration export/import contract

A small, versioned JSON bundle, produced/consumed entirely by
`scripts/install_camera_node.py` (no new tool):

```json
{
  "bundle_version": 1,
  "bundle_kind": "mockingbird_camera_node_config",
  "exported_at": "2026-08-21T12:00:00+00:00",
  "installed_build_id": "<manifest.json build_id, if available>",
  "node_env": {
    "MOCKINGBIRD_NODE_NAME": "Backyard Feeder Node",
    "MOCKINGBIRD_NODE_BIND": "0.0.0.0",
    "...": "the remaining portable node.env keys"
  }
}
```

`MOCKINGBIRD_NODE_PAIRING_STATE_PATH` is deliberately excluded and always
recomputed fresh for the importing install; `MOCKINGBIRD_NODE_TESTING` is
excluded as a test-only escape hatch. Import validates `bundle_version`
(refuses a newer-than-supported version honestly; accepts any older, valid
one), `bundle_kind`, and value safety (rejects an embedded newline/carriage
return/NUL, which could otherwise inject an extra line into an
`EnvironmentFile=`), and drops -- rather than fails on -- any unrecognized
key, so an older installer stays forward-compatible with a bundle written by
a newer one. Import only ever materializes `node.env` when one does not
already exist, extending rather than weakening the installer's existing
"never overwrite existing operator configuration" guarantee.

`mockingbird camera-node config export`'s closest existing convention is
`install_camera_node.py`'s own flag style (`--status`, `--rollback`), so
this reuses that: `--export-config PATH` (read-only) and `--import-config
PATH` (combinable with a normal install, or standalone on an
already-installed node).

## 4. Secrets

**Model A: export contains no reusable secret; reprovisioning always
performs fresh pairing.** `node.env` never contained a credential in the
first place -- the bearer credential is minted only inside `/pair`, hashed
before it ever touches the Node's own disk (`pairing.json`), and the raw
value lives only in the host's database. There is nothing to redact in the
export bundle; it is safe to inspect, copy, or store without special
handling. A same-hardware SD-card-died reinstall and a genuine hardware
replacement both go through the same live, explicit one-time-code pairing
either way -- restoring `node.env` only makes that pairing reattach to the
*right* logical camera automatically (see next section), never skips it.

## 5. Logical-vs-physical identity

`node_id` is `sha256(display_name)` -- a convenience compatibility
fingerprint, not a hardware serial. Restoring the same `MOCKINGBIRD_NODE_NAME`
via `--import-config` after a same-hardware reinstall reproduces the same
`node_id`, so ordinary repair-pairing reattaches with **no confirmation
needed at all** -- this is the golden path for "SD card died, same Pi/
camera." `CameraConfigurationEditResponse.node_expected_display_name`
surfaces this non-secret hint read-only so an operator setting up a
replacement can choose to name it identically on purpose.

For a genuine hardware swap (a different `node_id`, whether because the
prior config could not be restored or the operator deliberately renamed the
device), `confirm_node_identity_change: true` on the preview/apply request
is the explicit override. It never bypasses camera-availability/credential
validation -- only the one identity-equality check.

## 6. Provenance (schema 38)

Three additive, nullable columns on `camera_sources`, mirroring the boot-
identity migration's own shape exactly: `camera_node_prior_node_id`,
`camera_node_identity_replaced_at`, `camera_node_replacement_reason`.
Bounded "most recent transition only" -- never a growing hardware-asset
ledger. Written only inside the same transaction that confirms a
replacement, alongside clearing the *prior* physical node's boot-identity
facts (`camera_node_boot_id`/`camera_node_last_seen_at`/
`camera_node_boot_first_seen_at`/`camera_node_recent_boot_transitions_json`
-> `None`) so reviewed history never reads as if the new hardware produced
the old device's boot history; the new Node's own first real checkpoint
repopulates them honestly, the same as any Source that never had boot
identity tracked.

## 7. Capability rediscovery

Already structurally honest before this milestone: capability
(`node_capability_fingerprint`, advertised cameras/profiles) is always
resolved from a live pairing/health call, never cached from install time or
copied from a prior Source config. A confirmed replacement's `apply` reuses
the exact same live-verification path (`verify_camera=True`) first-run setup
already uses -- the new hardware's real capabilities are what get saved,
never an assumption carried over from the old device.

## 8. Zones / privacy

Zone `polygon_json` is normalized (0-1 fractional) with no persisted
reference resolution/aspect ratio -- there was never a baseline to diff a
replacement camera's framing against, for any Source, before this
milestone. Rather than fabricate a false "unchanged" claim, every confirmed
replacement unconditionally surfaces `zones_review_recommended: true` in the
preview and a bounded, time-windowed (7-day) Doctor `WARN` afterward,
honestly stating MockingBird cannot verify the replacement camera's
field of view matches the original. Zones/Privacy Zones themselves are
never deleted, rewritten, or bypassed by a replacement -- only flagged for
human review.

## 9. Rollback / interrupted recovery

Reuses the existing transactional `preview -> validate -> apply` pattern
verbatim (`session.begin()`, optimistic `state_token`/`preview_token`
concurrency checks, idempotency-key replay). A malformed import bundle is
validated before any filesystem write; a malformed/stale/conflicting
replacement request is rejected before any DB mutation. No new
rollback mechanism was needed because none of this milestone's writes are
allowed to happen outside that existing all-or-nothing boundary.

## 10. Doctor

One new bounded, lowest-priority check in `_interpret_camera_node`: a `WARN`
for a confirmed replacement within its 7-day review window (surfaces the
reason if one was given), falling through to the existing PASS/WARN ladder
otherwise -- never outranking a live offline/instability signal, and never
persisting forever once the window elapses.

## Files touched

- `src/mockingbird/storage/models.py`, `storage/database.py` (schema 38,
  the three provenance columns);
- `src/mockingbird/repository/product_repository.py` (guard relaxation,
  replacement detection/provenance write, edit-response surfacing);
- `src/mockingbird/api/schemas.py`, `api/main.py` (request/response fields,
  message text);
- `src/mockingbird/diagnostics/doctor.py` (the bounded replacement-review
  check);
- `scripts/install_camera_node.py` (`atomic_write_text`, export/import,
  the pre-existing non-atomic `node.env` write fixed as part of the same
  audit);
- `web/src/pages/CameraConfigurationPage.tsx`, `api/types.ts` (confirmation
  checkbox/reason field, impact/provenance surfacing);
- tests, and this document.

## Non-goals

- Cloud fleet management, external smart power/solar/BMS, managed PoE,
  custom replacement hardware, automatic physical camera calibration,
  dual-node redundancy, a full A/B OS-image update system -- unchanged from
  [roadmap.md](roadmap.md)'s existing post-v0.1 scope;
- rewriting historical Visit/Observation records to claim new hardware
  captured old evidence;
- a hardware asset-management system -- provenance stays bounded to the
  most recent transition;
- detector/species work, Gate C analytics, or a broad settings UI redesign.

## Validation tier

Tier 2 -- focused repository/API/installer/Doctor tests plus a schema
migration test; Core gate run once given this touches Camera Node
pairing/recovery persistence (see "Backend validation gates" in
[development-workflow.md](development-workflow.md)).
