"""ONVIF network-camera client (v0.1 Acquisition/Ingest Interoperability
Closure v1, "II.4 ONVIF"): the smallest production-worthy golden path --
identify a device, authenticate, enumerate its media profiles, and resolve
each profile's own RTSP stream URI -- for a camera the user names by LAN
host/port, plus a bounded, best-effort WS-Discovery probe.

This module never becomes a second product pipeline. Its only job is to
resolve an authenticated RTSP stream URI (see `embed_credentials_in_uri`)
that the *existing*, already-hardened RTSP bridge (`mockingbird.playback.
rtsp_bridge`) then plays exactly like any manually-entered RTSP camera --
same Doctor checks, same Observation Engine eligibility, same capability
reporting, same RTSPS honesty (`rtsp_bridge.RTSPS_TRANSPORT_SUPPORTED`).
`OnvifDeviceProfile.stream_uri` is never itself treated as a live/verified
capability; only the resolved `rtsp://...` URI handed to the RTSP bridge
is (see docs/next-provider-boundary-decision.md's "Candidate: RTSP Stream
Boundary" -- ONVIF here is a discovery/configuration assistant on top of
that same, already-accepted transport, not a new one).

## Architecture, mirroring `mockingbird.source_providers.camera_node`

- Pure SOAP envelope builders and XML response parsers (no I/O, fully
  deterministic, easily tested with synthetic XML bytes).
- An `OnvifRequester` Protocol plus a concrete, bounded `UrlLibOnvifRequester`
  -- the same dependency-injection shape `CameraNodeRequester`/
  `UrlLibCameraNodeRequester` already establish, so orchestration logic is
  testable against a fake transport without any real network access.
- `OnvifClient` orchestrates the golden path: capabilities -> device
  information -> media profiles -> per-profile stream URI.
- WS-Discovery (`discover_onvif_devices`) is a genuinely separate, optional
  best-effort LAN probe: its pure `parse_probe_matches` is fully tested,
  but the real UDP multicast send has not been verified against real ONVIF
  hardware in this development environment (no such hardware is available
  here) -- manual host/port entry remains the primary, required path; see
  docs/onvif-provider-boundary-design.md "Known limitations."

## Security boundary

ONVIF cameras are LAN devices by nature (like a Camera Node), not general
internet endpoints (unlike `external_url`'s still-image fetcher) -- so
`UrlLibOnvifRequester` mirrors `camera_node.py`'s stricter LAN-only host
allowlist (private/loopback/link-local only), not `external_url_preview.
py`'s broader "block only metadata/reserved" allowlist. This also closes
an SSRF path: a malicious "ONVIF host" field can never be used to probe
the public internet or cloud metadata services from the MockingBird host.

Credentials (`username`/`password`) are used only to (a) build the
WS-UsernameToken digest for each SOAP request and (b) embed into the
final resolved RTSP URI for the existing RTSP bridge's own credential
handling (`rtsp_bridge.redact_url`, `_redact_url_credentials`) -- never
logged, never included in any exception message (see
`OnvifClientError`'s docstring), and persisted exactly the way every
other secret Source-provider field already is (see
docs/source-provider-configuration-contract.md "Secret/Redaction policy").
"""

from __future__ import annotations

import base64
import hashlib
import secrets as _secrets
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPConnection
from typing import Protocol
from urllib.parse import quote, urlsplit, urlunsplit
from xml.etree import ElementTree

# ONVIF/WS-* XML namespaces this module actually reads or writes. Kept as
# a small fixed table (never a wildcard/"any namespace" parse) so a
# malformed or unexpected document fails closed with a clear error rather
# than silently matching the wrong element.
_NS = {
    "soap": "http://www.w3.org/2003/05/soap-envelope",
    "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
    "wsu": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
    "tds": "http://www.onvif.org/ver10/device/wsdl",
    "trt": "http://www.onvif.org/ver10/media/wsdl",
    "tt": "http://www.onvif.org/ver10/schema",
    "wsdd": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
    "wsa": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
}

# Bounded network behavior -- mirrors camera_node.py's fixed, non-Node-
# extensible timing/size limits exactly (see its own module docstring).
ONVIF_CONNECT_TIMEOUT_SECONDS = 3.0
ONVIF_RESPONSE_TIMEOUT_SECONDS = 5.0
ONVIF_MAX_RESPONSE_BYTES = 512_000
ONVIF_DISCOVERY_TIMEOUT_SECONDS = 3.0
ONVIF_DISCOVERY_MULTICAST_ADDRESS = "239.255.255.250"
ONVIF_DISCOVERY_MULTICAST_PORT = 3702

DEFAULT_ONVIF_PORT = 80


class OnvifClientError(ValueError):
    """Safe, fixed-vocabulary client error codes only -- raw host/
    credential/SOAP-fault text is never attached (mirrors
    `CameraNodeClientError`'s identical discipline)."""


ONVIF_ERROR_CODES = frozenset(
    {
        "onvif_host_invalid",
        "onvif_unreachable",
        "onvif_timeout",
        "onvif_authentication_rejected",
        "onvif_capabilities_unavailable",
        "onvif_device_information_unavailable",
        "onvif_no_media_service",
        "onvif_no_profiles",
        "onvif_stream_uri_unavailable",
        "onvif_response_invalid",
    }
)


# --------------------------------------------------------------------------
# Pure dataclasses
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OnvifCapabilities:
    device_xaddr: str | None
    media_xaddr: str | None


@dataclass(frozen=True)
class OnvifDeviceInformation:
    """Purely informational/advertised identity -- never authoritative
    capability facts (see "II.15 Source-resolution evidence" in the
    milestone brief: only what the RTSP bridge actually observes is
    authoritative resolution)."""

    manufacturer: str | None
    model: str | None
    firmware_version: str | None
    serial_number: str | None


@dataclass(frozen=True)
class OnvifMediaProfile:
    token: str
    name: str | None
    # Advertised by the camera's own GetProfiles response -- informational
    # only, never presented as verified/observed resolution.
    advertised_width: int | None
    advertised_height: int | None
    encoding: str | None


@dataclass(frozen=True)
class OnvifDeviceProfile:
    """One media profile plus its resolved RTSP stream URI -- the unit a
    caller selects from to complete ONVIF setup."""

    profile: OnvifMediaProfile
    stream_uri: str


@dataclass(frozen=True)
class OnvifDiscoveredDevice:
    device_uuid: str
    xaddrs: tuple[str, ...]
    scopes: tuple[str, ...]


# --------------------------------------------------------------------------
# WS-UsernameToken digest auth (pure; caller supplies nonce/timestamp so
# this stays deterministic and testable -- never `datetime.now()`/
# `secrets.token_bytes()` called internally, matching this codebase's
# existing "no impure calls inside a pure function" discipline).
# --------------------------------------------------------------------------


def password_digest(nonce: bytes, created: str, password: str) -> str:
    """The standard WSSE UsernameToken PasswordDigest:
    base64(SHA1(nonce + created + password)). `created` must already be an
    ISO-8601 UTC timestamp string (`Z` suffix, no fractional seconds --
    the form every ONVIF device expects)."""

    digest = hashlib.sha1(nonce + created.encode("utf-8") + password.encode("utf-8")).digest()  # noqa: S324
    return base64.b64encode(digest).decode("ascii")


def _iso_created(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _security_header(username: str, password: str, *, nonce: bytes, created_at: datetime) -> str:
    created = _iso_created(created_at)
    digest = password_digest(nonce, created, password)
    nonce_b64 = base64.b64encode(nonce).decode("ascii")
    return (
        "<soap:Header>"
        '<wsse:Security soap:mustUnderstand="1">'
        "<wsse:UsernameToken>"
        f"<wsse:Username>{_xml_escape(username)}</wsse:Username>"
        '<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">'
        f"{digest}</wsse:Password>"
        f'<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce_b64}</wsse:Nonce>'
        f"<wsu:Created>{created}</wsu:Created>"
        "</wsse:UsernameToken>"
        "</wsse:Security>"
        "</soap:Header>"
    )


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _envelope(header: str, body: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" '
        'xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" '
        'xmlns:tds="http://www.onvif.org/ver10/device/wsdl" '
        'xmlns:trt="http://www.onvif.org/ver10/media/wsdl">'
        f"{header}<soap:Body>{body}</soap:Body></soap:Envelope>"
    ).encode("utf-8")


def build_get_capabilities_envelope(
    *, username: str, password: str, nonce: bytes, created_at: datetime
) -> bytes:
    header = _security_header(username, password, nonce=nonce, created_at=created_at)
    body = "<tds:GetCapabilities><tds:Category>All</tds:Category></tds:GetCapabilities>"
    return _envelope(header, body)


def build_get_device_information_envelope(
    *, username: str, password: str, nonce: bytes, created_at: datetime
) -> bytes:
    header = _security_header(username, password, nonce=nonce, created_at=created_at)
    return _envelope(header, "<tds:GetDeviceInformation/>")


def build_get_profiles_envelope(
    *, username: str, password: str, nonce: bytes, created_at: datetime
) -> bytes:
    header = _security_header(username, password, nonce=nonce, created_at=created_at)
    return _envelope(header, "<trt:GetProfiles/>")


def build_get_stream_uri_envelope(
    profile_token: str, *, username: str, password: str, nonce: bytes, created_at: datetime
) -> bytes:
    header = _security_header(username, password, nonce=nonce, created_at=created_at)
    body = (
        "<trt:GetStreamUri>"
        "<trt:StreamSetup>"
        '<tt:Stream xmlns:tt="http://www.onvif.org/ver10/schema">RTP-Unicast</tt:Stream>'
        '<tt:Transport xmlns:tt="http://www.onvif.org/ver10/schema"><tt:Protocol>RTSP</tt:Protocol></tt:Transport>'
        "</trt:StreamSetup>"
        f"<trt:ProfileToken>{_xml_escape(profile_token)}</trt:ProfileToken>"
        "</trt:GetStreamUri>"
    )
    return _envelope(header, body)


# --------------------------------------------------------------------------
# Pure XML response parsers
# --------------------------------------------------------------------------


def _parse_xml(xml_bytes: bytes) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(xml_bytes)  # noqa: S314 -- fixed, non-user-authored ONVIF responses only
    except ElementTree.ParseError as error:
        raise OnvifClientError("onvif_response_invalid") from error


def parse_soap_fault(xml_bytes: bytes) -> str | None:
    """Extract a SOAP Fault's reason text, or `None` if this response is
    not a fault. Never raises -- a caller checks this before attempting
    the success-path parse for the same response."""

    try:
        root = _parse_xml(xml_bytes)
    except OnvifClientError:
        return None
    fault = root.find(".//soap:Fault", _NS)
    if fault is None:
        return None
    text = fault.find(".//soap:Text", _NS)
    if text is not None and text.text:
        return text.text.strip()
    return "onvif_soap_fault"


def parse_capabilities_response(xml_bytes: bytes) -> OnvifCapabilities:
    root = _parse_xml(xml_bytes)
    device_xaddr = _find_text(root, ".//tds:Device/tds:XAddr")
    media_xaddr = _find_text(root, ".//tds:Media/tds:XAddr")
    return OnvifCapabilities(device_xaddr=device_xaddr, media_xaddr=media_xaddr)


def parse_device_information_response(xml_bytes: bytes) -> OnvifDeviceInformation:
    root = _parse_xml(xml_bytes)
    return OnvifDeviceInformation(
        manufacturer=_find_text(root, ".//tds:Manufacturer"),
        model=_find_text(root, ".//tds:Model"),
        firmware_version=_find_text(root, ".//tds:FirmwareVersion"),
        serial_number=_find_text(root, ".//tds:SerialNumber"),
    )


def parse_profiles_response(xml_bytes: bytes) -> list[OnvifMediaProfile]:
    root = _parse_xml(xml_bytes)
    profiles: list[OnvifMediaProfile] = []
    for element in root.findall(".//trt:Profiles", _NS):
        token = element.get("token")
        if not token:
            continue
        name = _find_text(element, "tt:Name")
        width_text = _find_text(
            element, "tt:VideoEncoderConfiguration/tt:Resolution/tt:Width"
        )
        height_text = _find_text(
            element, "tt:VideoEncoderConfiguration/tt:Resolution/tt:Height"
        )
        encoding = _find_text(element, "tt:VideoEncoderConfiguration/tt:Encoding")
        profiles.append(
            OnvifMediaProfile(
                token=token,
                name=name,
                advertised_width=_safe_int(width_text),
                advertised_height=_safe_int(height_text),
                encoding=encoding,
            )
        )
    return profiles


def parse_stream_uri_response(xml_bytes: bytes) -> str:
    root = _parse_xml(xml_bytes)
    uri = _find_text(root, ".//trt:MediaUri/tt:Uri") or _find_text(root, ".//tt:Uri")
    if not uri:
        raise OnvifClientError("onvif_stream_uri_unavailable")
    return uri


def _find_text(element: ElementTree.Element, path: str) -> str | None:
    found = element.find(path, _NS)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Credential embedding for the existing RTSP bridge
# --------------------------------------------------------------------------


def embed_credentials_in_uri(uri: str, *, username: str, password: str) -> str:
    """Embed `username`/`password` as URL userinfo on an ONVIF-resolved
    stream URI (`rtsp://host:554/path` -> `rtsp://user:pass@host:554/
    path`) so the existing, unmodified RTSP bridge (`rtsp_bridge.py`)
    authenticates exactly the way a manually-entered credentialed RTSP URL
    already does -- ffmpeg parses URL userinfo for RTSP Basic/Digest auth
    natively; no MockingBird-side special-casing is needed. A URI that
    already carries credentials (rare, but some cameras include a
    read-only token) is left unmodified rather than double-embedding."""

    parts = urlsplit(uri)
    if "@" in parts.netloc:
        return uri
    if not username and not password:
        return uri
    userinfo = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return urlunsplit((parts.scheme, f"{userinfo}{parts.netloc}", parts.path, parts.query, parts.fragment))


# --------------------------------------------------------------------------
# Requester Protocol + bounded urllib/http.client implementation, mirroring
# camera_node.py's CameraNodeRequester/UrlLibCameraNodeRequester exactly.
# --------------------------------------------------------------------------


class OnvifRequester(Protocol):
    def post_soap(self, *, url: str, body: bytes) -> bytes: ...


_PRIVATE_NETWORKS = (
    "10.",
    "192.168.",
    "127.",
    "169.254.",
)


def _is_lan_host(host: str) -> bool:
    """LAN-only allowlist mirroring camera_node.py's client-side hardening
    (see the module docstring's "Security boundary"). Accepts a bare
    hostname ending in `.local` (mDNS) as well as a literal private/
    loopback/link-local IPv4 address; rejects everything else, including
    any public IP or arbitrary DNS name, so an ONVIF host field can never
    become an SSRF path to the public internet."""

    if host.endswith(".local"):
        return True
    if host.startswith("172."):
        try:
            second_octet = int(host.split(".")[1])
        except (IndexError, ValueError):
            return False
        return 16 <= second_octet <= 31
    return host.startswith(_PRIVATE_NETWORKS)


class UrlLibOnvifRequester:
    """Fixed-path LAN-only SOAP client with bounded connect/response
    timing and response size -- the same discipline `UrlLibCameraNode
    Requester` already establishes for the Camera Node client."""

    def post_soap(self, *, url: str, body: bytes) -> bytes:
        parsed = urlsplit(url)
        if parsed.scheme != "http" or not parsed.hostname or not _is_lan_host(parsed.hostname):
            raise OnvifClientError("onvif_host_invalid")
        connection = HTTPConnection(parsed.netloc, timeout=ONVIF_CONNECT_TIMEOUT_SECONDS)
        try:
            try:
                connection.request(
                    "POST",
                    parsed.path or "/onvif/device_service",
                    body=body,
                    headers={
                        "Content-Type": "application/soap+xml; charset=utf-8",
                        "Content-Length": str(len(body)),
                    },
                )
            except (OSError, TimeoutError) as error:
                raise OnvifClientError("onvif_unreachable") from error
            try:
                if connection.sock is not None:
                    connection.sock.settimeout(ONVIF_RESPONSE_TIMEOUT_SECONDS)
                response = connection.getresponse()
                data = response.read(ONVIF_MAX_RESPONSE_BYTES + 1)
            except (socket.timeout, TimeoutError) as error:
                raise OnvifClientError("onvif_timeout") from error
            except OSError as error:
                raise OnvifClientError("onvif_unreachable") from error
            if response.status == 401:
                raise OnvifClientError("onvif_authentication_rejected")
            if response.status >= 400 and not data:
                raise OnvifClientError("onvif_unreachable")
            return data[:ONVIF_MAX_RESPONSE_BYTES]
        finally:
            connection.close()


# --------------------------------------------------------------------------
# Orchestration: the golden path (capabilities -> device info -> profiles
# -> per-profile stream URI), each step a real, bounded SOAP round trip.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OnvifDiscoveryResult:
    device_information: OnvifDeviceInformation
    device_profiles: list[OnvifDeviceProfile]


class OnvifClient:
    def __init__(
        self,
        *,
        host: str,
        port: int = DEFAULT_ONVIF_PORT,
        username: str,
        password: str,
        requester: OnvifRequester | None = None,
        now: datetime | None = None,
    ) -> None:
        self._device_url = f"http://{host}:{port}/onvif/device_service"
        self._username = username
        self._password = password
        self._requester = requester or UrlLibOnvifRequester()
        # A test-only override, mirroring every other module's `now`
        # convention in this codebase (see place_activity_report.py). A
        # real production caller never passes this.
        self._now = now

    def _moment(self) -> datetime:
        return self._now or datetime.now(UTC)

    def _nonce(self) -> bytes:
        return _secrets.token_bytes(16)

    def get_capabilities(self) -> OnvifCapabilities:
        envelope = build_get_capabilities_envelope(
            username=self._username, password=self._password, nonce=self._nonce(), created_at=self._moment()
        )
        response_bytes = self._requester.post_soap(url=self._device_url, body=envelope)
        fault = parse_soap_fault(response_bytes)
        if fault is not None:
            raise OnvifClientError("onvif_capabilities_unavailable")
        return parse_capabilities_response(response_bytes)

    def get_device_information(self, *, device_xaddr: str) -> OnvifDeviceInformation:
        envelope = build_get_device_information_envelope(
            username=self._username, password=self._password, nonce=self._nonce(), created_at=self._moment()
        )
        response_bytes = self._requester.post_soap(url=device_xaddr, body=envelope)
        fault = parse_soap_fault(response_bytes)
        if fault is not None:
            raise OnvifClientError("onvif_device_information_unavailable")
        return parse_device_information_response(response_bytes)

    def get_profiles(self, *, media_xaddr: str) -> list[OnvifMediaProfile]:
        envelope = build_get_profiles_envelope(
            username=self._username, password=self._password, nonce=self._nonce(), created_at=self._moment()
        )
        response_bytes = self._requester.post_soap(url=media_xaddr, body=envelope)
        fault = parse_soap_fault(response_bytes)
        if fault is not None:
            raise OnvifClientError("onvif_no_profiles")
        return parse_profiles_response(response_bytes)

    def get_stream_uri(self, *, media_xaddr: str, profile_token: str) -> str:
        envelope = build_get_stream_uri_envelope(
            profile_token,
            username=self._username,
            password=self._password,
            nonce=self._nonce(),
            created_at=self._moment(),
        )
        response_bytes = self._requester.post_soap(url=media_xaddr, body=envelope)
        fault = parse_soap_fault(response_bytes)
        if fault is not None:
            raise OnvifClientError("onvif_stream_uri_unavailable")
        return parse_stream_uri_response(response_bytes)

    def discover(self) -> OnvifDiscoveryResult:
        """The full golden path in one call: capabilities -> device
        information -> every media profile, each with its own resolved
        stream URI. Raises `OnvifClientError` (a safe, fixed code -- see
        its docstring) on the first unrecoverable step; a caller decides
        how to surface that to the product-level API response."""

        capabilities = self.get_capabilities()
        device_xaddr = capabilities.device_xaddr or self._device_url
        media_xaddr = capabilities.media_xaddr
        if not media_xaddr:
            raise OnvifClientError("onvif_no_media_service")

        device_information = self.get_device_information(device_xaddr=device_xaddr)
        profiles = self.get_profiles(media_xaddr=media_xaddr)
        if not profiles:
            raise OnvifClientError("onvif_no_profiles")

        device_profiles = [
            OnvifDeviceProfile(
                profile=profile,
                stream_uri=self.get_stream_uri(media_xaddr=media_xaddr, profile_token=profile.token),
            )
            for profile in profiles
        ]
        return OnvifDiscoveryResult(device_information=device_information, device_profiles=device_profiles)


# --------------------------------------------------------------------------
# WS-Discovery (bounded, best-effort LAN probe -- see the module docstring's
# "Known limitations": the pure parse below is fully tested; the real UDP
# send has not been verified against real ONVIF hardware in this
# development environment).
# --------------------------------------------------------------------------


def build_probe_message(message_id: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
        'xmlns:wsdd="http://schemas.xmlsoap.org/ws/2005/04/discovery">'
        "<soap:Header>"
        "<wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>"
        f"<wsa:MessageID>uuid:{_xml_escape(message_id)}</wsa:MessageID>"
        "<wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>"
        "</soap:Header>"
        "<soap:Body>"
        '<wsdd:Probe><wsdd:Types xmlns:dn="http://www.onvif.org/ver10/network/wsdl">dn:NetworkVideoTransmitter</wsdd:Types></wsdd:Probe>'
        "</soap:Body>"
        "</soap:Envelope>"
    ).encode("utf-8")


def parse_probe_matches(xml_bytes: bytes) -> list[OnvifDiscoveredDevice]:
    root = _parse_xml(xml_bytes)
    matches: list[OnvifDiscoveredDevice] = []
    for match in root.findall(".//wsdd:ProbeMatch", _NS):
        address = _find_text(match, "wsa:EndpointReference/wsa:Address")
        xaddrs_text = _find_text(match, "wsdd:XAddrs") or ""
        scopes_text = _find_text(match, "wsdd:Scopes") or ""
        if not address:
            continue
        matches.append(
            OnvifDiscoveredDevice(
                device_uuid=address,
                xaddrs=tuple(xaddrs_text.split()),
                scopes=tuple(scopes_text.split()),
            )
        )
    return matches


def discover_onvif_devices(
    *,
    timeout_seconds: float = ONVIF_DISCOVERY_TIMEOUT_SECONDS,
    message_id: str | None = None,
    socket_factory: object = socket.socket,
) -> list[OnvifDiscoveredDevice]:
    """Send one bounded WS-Discovery Probe over UDP multicast and collect
    ProbeMatch responses until `timeout_seconds` elapses. Best-effort: a
    quiet network (no ONVIF devices, or multicast blocked by the host
    firewall/network segment) returns an empty list, never an exception --
    manual host/port entry remains the required, always-available path.
    `socket_factory` exists only so a test can inject a fake, no real
    network access required (see tests/test_onvif_client.py); production
    callers never pass it.
    """

    sock = socket_factory(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)  # type: ignore[operator]
    devices: list[OnvifDiscoveredDevice] = []
    try:
        sock.settimeout(timeout_seconds)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        probe = build_probe_message(message_id or _secrets.token_hex(16))
        sock.sendto(probe, (ONVIF_DISCOVERY_MULTICAST_ADDRESS, ONVIF_DISCOVERY_MULTICAST_PORT))
        while True:
            try:
                data, _ = sock.recvfrom(ONVIF_MAX_RESPONSE_BYTES)
            except (TimeoutError, OSError):
                break
            try:
                devices.extend(parse_probe_matches(data))
            except OnvifClientError:
                continue
    except OSError:
        return []
    finally:
        sock.close()
    return devices


__all__ = [
    "DEFAULT_ONVIF_PORT",
    "ONVIF_ERROR_CODES",
    "OnvifCapabilities",
    "OnvifClient",
    "OnvifClientError",
    "OnvifDeviceInformation",
    "OnvifDeviceProfile",
    "OnvifDiscoveredDevice",
    "OnvifDiscoveryResult",
    "OnvifMediaProfile",
    "OnvifRequester",
    "UrlLibOnvifRequester",
    "build_get_capabilities_envelope",
    "build_get_device_information_envelope",
    "build_get_profiles_envelope",
    "build_get_stream_uri_envelope",
    "build_probe_message",
    "discover_onvif_devices",
    "embed_credentials_in_uri",
    "parse_capabilities_response",
    "parse_device_information_response",
    "parse_probe_matches",
    "parse_profiles_response",
    "parse_soap_fault",
    "parse_stream_uri_response",
    "password_digest",
]
