"""Camera / Source + Multi-Camera Maturity v1, Phase D: a single, bounded,
truthful compatibility classification for each Source provider a user can
select (Add Camera, or the existing "Provider setup" edit flow on the
Streams page).

This reconciles five independently-defined, disagreeing "provider maturity"
vocabularies this milestone's own archaeology found already in the
codebase: `SourceProviderKind`, `SourceProviderDefinitionStatus`,
`readiness_level`, `mockingbird.observation.unified_status.
PROVIDER_SUPPORT_MATRIX`, and `CameraSetupOption.availability`. None of them
distinguish "fully built, permanently non-live by design" (folder/webhook
import) from "not yet built at all" (`rtsp_future`/`esp32_future`/
`browser_camera_future`) -- today they share one token
(`"future_adapter"`/`observation_unavailable`), which under-claims a real,
tested import path as equivalent to vaporware. `PROVIDER_SUPPORT_MATRIX`
specifically answers a narrower question ("does live Observation Engine
analysis run on this") that is correctly "no" for every import-only
provider by design -- this module answers the broader, user-facing
question instead.

Five bounded levels, chosen to answer one question honestly: how much can a
user trust this provider to do what its name suggests, right now?

- ``"certified"``: the flagship, most field-tested, hardware-verified live
  path. Never assigned merely because a provider key exists (the milestone
  brief's own explicit warning) -- only `camera_node` qualifies, and only
  because of its own real acceptance history (Camera Node Installer v1,
  Windows Runtime Recovery + Camera Node Connectivity Proof, repeated real
  reboot/outage/reprovision field verification).
- ``"compatible"``: fully built and genuinely usable, real live capability,
  reasonably proven but without that same depth of field history.
- ``"experimental"``: real, working code exists, but is narrower or less
  proven than "compatible" -- not a placeholder, not the default
  recommendation.
- ``"import_only"``: fully built, but deliberately, permanently non-live by
  design (offline/recorded media or metadata ingest, never a missing
  feature).
- ``"unsupported"``: no real implementation exists yet -- a
  placeholder/future contract only (a disabled option, not a working one).

Pure and dependency-light, matching this package's established "pure
decision module" convention -- reused as-is by both `ProductRepository`
(API responses) and any future presentation surface; never re-derived ad
hoc per caller.
"""

from __future__ import annotations

from typing import Literal

ProviderCompatibility = Literal["certified", "compatible", "experimental", "import_only", "unsupported"]

#: Curated, disclosed, one-place classification -- see the module docstring
#: for what each level means and why. A provider key absent here (a future,
#: genuinely unknown key) honestly falls back to "unsupported" rather than
#: guessing.
_PROVIDER_COMPATIBILITY: dict[str, ProviderCompatibility] = {
    "camera_node": "certified",
    "external_url": "compatible",  # covers both plain still-image preview and RTSP live playback.
    "onvif": "compatible",  # a discovery assist over the same external_url/RTSP path once resolved.
    "local_usb": "compatible",
    "manual_media": "import_only",
    "folder_import_future": "import_only",
    "webhook_future": "experimental",
    "microphone": "compatible",  # real, accepted BirdNET-class acoustic runtime -- not a camera, still fully built.
    "demo": "experimental",  # a real, working sample path -- never the product's real camera answer.
    "rtsp_future": "unsupported",
    "esp32_future": "unsupported",
    "browser_camera_future": "unsupported",
}

#: Plain, ordinary-language labels -- never shown as raw enum tokens.
_COMPATIBILITY_LABELS: dict[ProviderCompatibility, str] = {
    "certified": "Certified",
    "compatible": "Compatible",
    "experimental": "Experimental",
    "import_only": "Import only",
    "unsupported": "Unsupported",
}


def classify_provider_compatibility(provider_key: str | None) -> ProviderCompatibility:
    """Honest, code-grounded compatibility level for one provider key.
    Never claims "certified" merely because a provider key exists."""

    return _PROVIDER_COMPATIBILITY.get(provider_key or "", "unsupported")


def provider_compatibility_label(compatibility: ProviderCompatibility) -> str:
    return _COMPATIBILITY_LABELS[compatibility]
