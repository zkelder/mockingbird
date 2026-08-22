# ONVIF Provider Boundary Design

v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.4 ONVIF"). See
also [next-provider-boundary-decision.md](next-provider-boundary-decision.md)
(the earlier evaluation this supersedes for RTSP/ONVIF specifically),
[source-adapter-boundary-design.md](source-adapter-boundary-design.md),
[source-provider-configuration-contract.md](source-provider-configuration-contract.md),
and [stream-source-playback-contract.md](stream-source-playback-contract.md).

## Purpose

MockingBird is hardware- and provider-agnostic (settled direction, see
"Scope-reopening rule" in [roadmap.md](roadmap.md)). Before this milestone,
a network camera could only be added by a user who already knew its raw
RTSP URL. ONVIF (a standard many IP cameras implement) lets MockingBird
instead: discover/identify a device, authenticate, enumerate its media
profiles, and resolve a playable stream URI -- without the user hand-typing
an RTSP path. This is a discovery/configuration assistant, not a second
observational pipeline.

## Architecture invariant: converge immediately, never fork

RTSP browser playback already existed before this milestone (Phases 19-22
-- a real, working ffmpeg-based RTSP-to-MJPEG bridge,
`mockingbird.playback.rtsp_bridge`, reached through the `external_url`
Source provider's `live_stream_type="rtsp"` config, complete with a live
HTTP endpoint, Doctor diagnostics, and Observation Engine eligibility). The
one architectural rule this milestone enforces for ONVIF: **it must not
become a second live-playback/monitoring pipeline.**

```
Add camera -> ONVIF discovery (host/port/credentials)
           -> capabilities -> device information -> media profiles
           -> per-profile stream URI (mockingbird.source_providers.onvif_client)
           -> user selects one profile
           -> credential embedded into the stream URI, client-side
           -> persisted as an ordinary provider_key="external_url",
              live_stream_type="rtsp" Source
           -> from here, indistinguishable from a manually-entered RTSP
              camera: same rtsp_bridge, same Doctor check, same
              Observation Engine eligibility, same RTSPS honesty
```

`camera_onvif_profiles` (schema v39, `CameraOnvifProfileModel`) exists
*only* to remember which device/profile a Source was configured through --
bounded, informational provenance (device manufacturer/model/firmware,
profile token, advertised resolution), read back only for display
("connected via ONVIF") -- never authoritative over playback readiness,
capability, or truth. The real playback configuration always lives in the
same `SourceProviderConfigurationModel` row every other RTSP camera uses.

## Golden path implemented

1. **Discover** -- `POST /api/onvif/discover-profiles` (stateless, no
   Source required; side-effect-free, matching every other provider's
   status/preview discipline -- see
   [source-connection-provider-contract.md](source-connection-provider-contract.md)).
   Takes `onvif_host`/`onvif_port`/`onvif_username`/`onvif_password`.
2. **Identify + authenticate + enumerate profiles** --
   `OnvifClient.discover()` in
   `src/mockingbird/source_providers/onvif_client.py`: a real bounded SOAP
   round trip per step (`GetCapabilities` -> `GetDeviceInformation` ->
   `GetProfiles` -> `GetStreamUri` per profile), WS-UsernameToken
   `PasswordDigest` authentication (pure, deterministic, fully unit-tested
   -- see `tests/test_onvif_client.py`).
3. **Select** -- the frontend (`CameraSetupPage.tsx`'s ONVIF sub-flow)
   renders the returned profiles (name, advertised resolution, encoding);
   the user picks one.
4. **Persist** -- `POST /api/sources/{source_id}/onvif/record-profile`
   writes the ordinary `external_url`+rtsp provider configuration (via the
   existing `update_source_provider_configuration`) plus the
   `camera_onvif_profiles` provenance row, and corrects
   `CameraSourceModel.kind` to `"rtsp"` so Doctor's ffmpeg-dependency
   check -- which reads `.kind` directly -- stays honest regardless of
   what kind the Source started as.
5. **Validate stream / begin monitoring** -- unchanged: the existing
   `StreamPlaybackStatus`/RTSP bridge/Observation Engine machinery, now
   additionally annotated with `onvif_connected`/`onvif_device_summary`
   (purely informational).

## Security boundary

- **LAN-only host validation.** ONVIF cameras are LAN devices by nature
  (like a Camera Node), not general internet endpoints (unlike
  `external_url`'s still-image fetcher, which instead blocks only
  metadata/reserved addresses while allowing RFC1918). `UrlLibOnvifRequester`
  mirrors `mockingbird.source_providers.camera_node`'s stricter allowlist:
  private/loopback/link-local IPv4 ranges and `.local` hostnames only.
  This closes an SSRF path -- a malicious "ONVIF host" field can never
  reach the public internet or a cloud metadata endpoint from the
  MockingBird host.
- **Credentials never appear in a discovery response.** `POST
  /api/onvif/discover-profiles` returns each profile's *bare* stream URI
  (as the camera itself reports it) -- never credential-embedded. The
  frontend, which already holds the raw password in its own form state,
  embeds it into the URI client-side
  (`embedOnvifCredentials`/`embed_credentials_in_uri`, kept in exact sync
  between `CameraSetupPage.tsx` and `onvif_client.py`) only once, at
  selection time -- the same discipline
  [source-provider-configuration-contract.md](source-provider-configuration-contract.md)'s
  "Secret/Redaction policy" already requires for every other provider.
- **A real, generic credential-redaction gap was found and fixed by this
  milestone**, not specific to ONVIF: `_source_provider_configuration_
  from_config`'s embedded-URL-credential redaction was hardcoded to
  exactly one field key (`external_url`'s `live_stream_url`). Any other
  non-secret URL-shaped field (for example the plain snapshot `url`
  field) round-tripped embedded `user:pass@host` credentials in
  plaintext through `safe_config_preview`. Fixed generally --
  `_redact_url_credentials` now applies to every non-secret field value
  (it is a safe no-op for a value that is not itself a credentialed URL)
  -- with a symmetric fix in `_sanitize_source_provider_config` so a
  caller round-tripping the now-redacted preview string can never
  overwrite the real stored value with the redacted placeholder.
  Confirmed via the full pre-existing provider-configuration test suite
  (217 tests unaffected) plus new regressions.

## RTSPS: explicitly not faked

`rtsp_bridge.RTSPS_TRANSPORT_SUPPORTED = False` -- an evidence-based,
documented constant, not a guess. This deployment's ffmpeg (6.1.1,
`--enable-gnutls`) was tested directly: opening an `rtsps://` URL, with or
without forcing `-rtsp_transport tcp`, still establishes a **plain
`tcp://`** connection identical to `rtsp://`. The RTSP demuxer does not
upgrade transport based on URL scheme in this configuration. Serving an
`rtsps://`-configured camera as if it were secure would be a real,
concrete honesty defect (a user believing their connection is encrypted
when it is not) -- so it is refused, explicitly and audibly, at three
layers: `StreamPlaybackStatus` (`rtsp_bridge_status="rtsps_unsupported"`),
the backend live-session-start validator, and `build_rtsp_mjpeg_command`
itself (`RtspsUnsupportedError`, defense in depth). This is a genuine,
disclosed transport-stack limitation, revisited only alongside a
deliberate, reviewed change to how the bridge invokes ffmpeg (an explicit
TLS lower-transport, or a dependency change) -- never by flipping the
constant alone.

## WS-Discovery: implemented, unverified against real hardware

`onvif_client.discover_onvif_devices` sends a bounded UDP multicast WS-
Discovery Probe and collects `ProbeMatch` responses. The XML message
building/parsing is pure and fully unit-tested against synthetic
responses. The real multicast send/receive has **not** been verified
against a real ONVIF camera -- no such hardware is available in this
development environment (the same honesty standard applied to RTSPS
above: implemented and structurally sound, not falsely claimed as field-
proven). Manual host/port entry remains the primary, always-available
path; this function is best-effort and returns an empty list (never
raises) on a quiet network. It is not yet wired into the frontend
discovery form -- the smallest named follow-up, should real-hardware
evidence justify it.

## Capability reporting

`StreamPlaybackStatus.onvif_connected`/`onvif_device_summary` (purely
informational, additive) is the only new capability-facing surface;
everything else (`rtsp_bridge_required`/`available`/`status`,
`supports_live_playback`) is the pre-existing RTSP contract, unchanged.
`advertised_width`/`advertised_height` on a discovered profile are the
camera's own self-reported, unverified claim -- never presented as
observed/verified resolution (see "II.15 Source-resolution evidence": only
what the RTSP bridge actually receives is authoritative).

## Error taxonomy

`OnvifClientError` (mirrors `CameraNodeClientError`'s exact discipline --
safe, fixed-vocabulary codes only, raw host/credential/SOAP-fault text
never attached): `onvif_host_invalid`, `onvif_unreachable`,
`onvif_timeout`, `onvif_authentication_rejected`,
`onvif_capabilities_unavailable`, `onvif_device_information_unavailable`,
`onvif_no_media_service`, `onvif_no_profiles`,
`onvif_stream_uri_unavailable`, `onvif_response_invalid`. Mapped to one of
`OnvifDiscoverProfilesResponse.status` (`available`/`unreachable`/
`authentication_rejected`/`no_profiles`/`error`) plus an actionable,
credential-free message -- never a generic "camera broken" for every
failure.

## Explicitly not built here

- Full WS-Discovery UI wiring (see "WS-Discovery" above).
- PTZ, audio, or any ONVIF capability beyond media-profile stream
  resolution -- out of scope; "do not build an enterprise VMS."
- A second live-playback pipeline -- explicitly, deliberately avoided by
  the convergence architecture above.
- Per-frame decode of ONVIF/RTSP streams beyond what the existing
  Observation Engine already does for any live Stream -- unaffected,
  unchanged, and out of scope for this milestone.

## Tests

- `tests/test_onvif_client.py` -- pure SOAP envelope/parser/digest-auth
  tests, LAN-host-allowlist tests, `OnvifClient` orchestration against an
  injected fake transport (no real network), WS-Discovery parse + a
  bounded fake-socket send/receive test.
- ONVIF scenarios in `tests/test_stream_playback_contract.py` --
  discovery/record-profile API integration, credential-redaction
  regression, RTSPS refusal regression, `CameraSourceModel.kind`
  correction regression, provider-definition secrecy regression.
- `web/e2e/camera-setup-onvif.spec.ts` -- the guided setup UI flow
  (discover -> select profile -> Check camera settings -> Finish enabled),
  and the authentication-rejected path, against a real running backend
  with a mocked ONVIF transport.
