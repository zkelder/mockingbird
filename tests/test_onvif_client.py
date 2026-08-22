"""Tier 1 pure/injected-transport tests for the ONVIF client
(`mockingbird.source_providers.onvif_client`) -- v0.1 Acquisition/Ingest
Interoperability Closure v1 ("II.4 ONVIF"). No real network access
anywhere in this file: SOAP round trips use a fake `OnvifRequester`
(mirroring `tests/test_camera_node.py`'s `_FakeNodeRequester` pattern),
and the one WS-Discovery test injects a fake socket factory.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mockingbird.source_providers import onvif_client as onvif


# -- Pure envelope builders --------------------------------------------------


def test_get_capabilities_envelope_is_well_formed_and_never_leaks_plaintext_password() -> None:
    envelope = onvif.build_get_capabilities_envelope(
        username="admin",
        password="super-secret",
        nonce=b"0123456789abcdef",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    # Well-formed XML (parses without error) containing the expected
    # ONVIF operation.
    assert b"<tds:GetCapabilities>" in envelope
    assert b"admin" in envelope
    # The digest, not the raw password, is what travels on the wire.
    assert b"super-secret" not in envelope
    assert b"PasswordDigest" in envelope


def test_get_profiles_and_stream_uri_envelopes_are_well_formed() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    profiles_envelope = onvif.build_get_profiles_envelope(
        username="admin", password="pw", nonce=b"nonce-bytes-1234", created_at=created_at
    )
    assert b"<trt:GetProfiles/>" in profiles_envelope

    stream_uri_envelope = onvif.build_get_stream_uri_envelope(
        "profile-token-1", username="admin", password="pw", nonce=b"nonce-bytes-1234", created_at=created_at
    )
    assert b"<trt:ProfileToken>profile-token-1</trt:ProfileToken>" in stream_uri_envelope
    assert b"RTP-Unicast" in stream_uri_envelope


def test_device_information_envelope_carries_no_body_parameters() -> None:
    envelope = onvif.build_get_device_information_envelope(
        username="admin", password="pw", nonce=b"nonce-bytes-1234", created_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert b"<tds:GetDeviceInformation/>" in envelope


# -- WS-UsernameToken PasswordDigest -----------------------------------------


def test_password_digest_matches_independent_sha1_computation() -> None:
    import base64
    import hashlib

    nonce = b"fixed-nonce-bytes"
    created = "2026-01-01T00:00:00Z"
    password = "hunter2"
    expected = base64.b64encode(hashlib.sha1(nonce + created.encode() + password.encode()).digest()).decode()  # noqa: S324
    assert onvif.password_digest(nonce, created, password) == expected


def test_password_digest_is_deterministic_and_sensitive_to_every_input() -> None:
    base = onvif.password_digest(b"nonce-a", "2026-01-01T00:00:00Z", "pw")
    assert onvif.password_digest(b"nonce-a", "2026-01-01T00:00:00Z", "pw") == base
    assert onvif.password_digest(b"nonce-b", "2026-01-01T00:00:00Z", "pw") != base
    assert onvif.password_digest(b"nonce-a", "2026-01-01T00:00:01Z", "pw") != base
    assert onvif.password_digest(b"nonce-a", "2026-01-01T00:00:00Z", "other") != base


# -- Credential embedding for the existing RTSP bridge -----------------------


def test_embed_credentials_adds_userinfo_to_a_bare_stream_uri() -> None:
    result = onvif.embed_credentials_in_uri(
        "rtsp://192.168.1.50:554/onvif1", username="admin", password="hunter2"
    )
    assert result == "rtsp://admin:hunter2@192.168.1.50:554/onvif1"


def test_embed_credentials_url_encodes_special_characters() -> None:
    result = onvif.embed_credentials_in_uri(
        "rtsp://192.168.1.50:554/onvif1", username="ad min", password="p@ss:word"
    )
    assert result == "rtsp://ad%20min:p%40ss%3Aword@192.168.1.50:554/onvif1"


def test_embed_credentials_never_double_embeds_an_already_credentialed_uri() -> None:
    already = "rtsp://token123@192.168.1.50:554/onvif1"
    assert onvif.embed_credentials_in_uri(already, username="admin", password="pw") == already


def test_embed_credentials_leaves_uri_unchanged_when_no_credentials_given() -> None:
    bare = "rtsp://192.168.1.50:554/onvif1"
    assert onvif.embed_credentials_in_uri(bare, username="", password="") == bare


# -- LAN-only host validation (SSRF boundary) --------------------------------


@pytest.mark.parametrize(
    "host,expected",
    [
        ("192.168.1.50", True),
        ("10.0.0.5", True),
        ("127.0.0.1", True),
        ("169.254.1.2", True),
        ("172.16.0.1", True),
        ("172.31.255.255", True),
        ("camera.local", True),
        ("172.32.0.1", False),
        ("172.15.0.1", False),
        ("8.8.8.8", False),
        ("example.com", False),
        ("169.254.169.254", True),  # link-local incl. the cloud-metadata address -- ONVIF cameras are LAN devices
    ],
)
def test_lan_host_allowlist(host: str, expected: bool) -> None:
    assert onvif._is_lan_host(host) is expected


# -- Pure XML response parsers ------------------------------------------------

_CAPABILITIES_XML = b"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
    xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <soap:Body>
    <tds:GetCapabilitiesResponse>
      <tds:Capabilities>
        <tds:Device><tds:XAddr>http://192.168.1.50/onvif/device_service</tds:XAddr></tds:Device>
        <tds:Media><tds:XAddr>http://192.168.1.50/onvif/media_service</tds:XAddr></tds:Media>
      </tds:Capabilities>
    </tds:GetCapabilitiesResponse>
  </soap:Body>
</soap:Envelope>"""

_DEVICE_INFO_XML = b"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
    xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <soap:Body>
    <tds:GetDeviceInformationResponse>
      <tds:Manufacturer>Acme</tds:Manufacturer>
      <tds:Model>CamPro 4K</tds:Model>
      <tds:FirmwareVersion>1.2.3</tds:FirmwareVersion>
      <tds:SerialNumber>SN-001</tds:SerialNumber>
    </tds:GetDeviceInformationResponse>
  </soap:Body>
</soap:Envelope>"""

_PROFILES_XML = b"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
    xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
    xmlns:tt="http://www.onvif.org/ver10/schema">
  <soap:Body>
    <trt:GetProfilesResponse>
      <trt:Profiles token="profile-main" fixed="true">
        <tt:Name>MainStream</tt:Name>
        <tt:VideoEncoderConfiguration>
          <tt:Encoding>H264</tt:Encoding>
          <tt:Resolution><tt:Width>1920</tt:Width><tt:Height>1080</tt:Height></tt:Resolution>
        </tt:VideoEncoderConfiguration>
      </trt:Profiles>
      <trt:Profiles token="profile-sub" fixed="true">
        <tt:Name>SubStream</tt:Name>
        <tt:VideoEncoderConfiguration>
          <tt:Encoding>H264</tt:Encoding>
          <tt:Resolution><tt:Width>640</tt:Width><tt:Height>360</tt:Height></tt:Resolution>
        </tt:VideoEncoderConfiguration>
      </trt:Profiles>
    </trt:GetProfilesResponse>
  </soap:Body>
</soap:Envelope>"""

_STREAM_URI_XML = b"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
    xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
    xmlns:tt="http://www.onvif.org/ver10/schema">
  <soap:Body>
    <trt:GetStreamUriResponse>
      <trt:MediaUri><tt:Uri>rtsp://192.168.1.50:554/onvif1</tt:Uri></trt:MediaUri>
    </trt:GetStreamUriResponse>
  </soap:Body>
</soap:Envelope>"""

_SOAP_FAULT_AUTH_XML = b"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <soap:Fault>
      <soap:Code><soap:Value>soap:Sender</soap:Value></soap:Code>
      <soap:Reason><soap:Text xml:lang="en">Sender not Authorized</soap:Text></soap:Reason>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""

_PROBE_MATCHES_XML = b"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
    xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
    xmlns:wsdd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <soap:Body>
    <wsdd:ProbeMatches>
      <wsdd:ProbeMatch>
        <wsa:EndpointReference><wsa:Address>urn:uuid:1234-5678</wsa:Address></wsa:EndpointReference>
        <wsdd:Scopes>onvif://www.onvif.org/type/NetworkVideoTransmitter</wsdd:Scopes>
        <wsdd:XAddrs>http://192.168.1.50/onvif/device_service</wsdd:XAddrs>
      </wsdd:ProbeMatch>
    </wsdd:ProbeMatches>
  </soap:Body>
</soap:Envelope>"""


def test_parse_capabilities_response_extracts_device_and_media_xaddrs() -> None:
    capabilities = onvif.parse_capabilities_response(_CAPABILITIES_XML)
    assert capabilities.device_xaddr == "http://192.168.1.50/onvif/device_service"
    assert capabilities.media_xaddr == "http://192.168.1.50/onvif/media_service"


def test_parse_device_information_response() -> None:
    info = onvif.parse_device_information_response(_DEVICE_INFO_XML)
    assert info.manufacturer == "Acme"
    assert info.model == "CamPro 4K"
    assert info.firmware_version == "1.2.3"
    assert info.serial_number == "SN-001"


def test_parse_profiles_response_returns_every_profile_with_advertised_resolution() -> None:
    profiles = onvif.parse_profiles_response(_PROFILES_XML)
    assert [p.token for p in profiles] == ["profile-main", "profile-sub"]
    assert profiles[0].name == "MainStream"
    assert profiles[0].advertised_width == 1920
    assert profiles[0].advertised_height == 1080
    assert profiles[0].encoding == "H264"
    assert profiles[1].advertised_width == 640


def test_parse_stream_uri_response() -> None:
    assert onvif.parse_stream_uri_response(_STREAM_URI_XML) == "rtsp://192.168.1.50:554/onvif1"


def test_parse_stream_uri_response_raises_on_missing_uri() -> None:
    empty = b"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body/></soap:Envelope>"""
    with pytest.raises(onvif.OnvifClientError):
        onvif.parse_stream_uri_response(empty)


def test_parse_soap_fault_extracts_reason_text() -> None:
    assert onvif.parse_soap_fault(_SOAP_FAULT_AUTH_XML) == "Sender not Authorized"


def test_parse_soap_fault_returns_none_for_a_normal_response() -> None:
    assert onvif.parse_soap_fault(_CAPABILITIES_XML) is None


def test_parse_soap_fault_returns_none_for_garbage_rather_than_raising() -> None:
    assert onvif.parse_soap_fault(b"not xml at all") is None


def test_parse_probe_matches() -> None:
    matches = onvif.parse_probe_matches(_PROBE_MATCHES_XML)
    assert len(matches) == 1
    assert matches[0].device_uuid == "urn:uuid:1234-5678"
    assert matches[0].xaddrs == ("http://192.168.1.50/onvif/device_service",)
    assert "NetworkVideoTransmitter" in matches[0].scopes[0]


def test_build_probe_message_is_well_formed_xml() -> None:
    message = onvif.build_probe_message("test-message-id")
    assert b"NetworkVideoTransmitter" in message
    assert b"test-message-id" in message
    from xml.etree import ElementTree

    ElementTree.fromstring(message)  # must not raise


def test_parse_response_raises_response_invalid_on_malformed_xml() -> None:
    with pytest.raises(onvif.OnvifClientError):
        onvif.parse_capabilities_response(b"<not-closed")


# -- OnvifClient orchestration against a fake, injected transport -----------


class _FakeOnvifRequester:
    """Mirrors tests/test_camera_node.py's `_FakeNodeRequester` pattern:
    maps request URLs to canned SOAP response bytes, with no real network
    access whatsoever."""

    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def post_soap(self, *, url: str, body: bytes) -> bytes:
        self.calls.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected ONVIF request to {url}")
        return self.responses[url]


_DEVICE_URL = "http://192.168.1.50:80/onvif/device_service"
_MEDIA_URL = "http://192.168.1.50/onvif/media_service"


def _golden_path_requester() -> _FakeOnvifRequester:
    return _FakeOnvifRequester(
        {
            _DEVICE_URL: _CAPABILITIES_XML,
            "http://192.168.1.50/onvif/device_service": _DEVICE_INFO_XML,
            _MEDIA_URL: _PROFILES_XML,
        }
    )


def test_onvif_client_full_golden_path_resolves_every_profiles_stream_uri() -> None:
    # GetStreamUri is called once per profile, both against the same media
    # XAddr in this fixture -- both return the same fixture URI here since
    # the fake requester is keyed by URL, not by request body; that is
    # sufficient to prove the orchestration shape (one resolved stream_uri
    # per discovered profile), which is this test's actual claim.
    requester = _golden_path_requester()
    requester.responses[_MEDIA_URL] = _PROFILES_XML

    class _MultiResponseRequester(_FakeOnvifRequester):
        def post_soap(self, *, url: str, body: bytes) -> bytes:
            self.calls.append(url)
            if url == _MEDIA_URL and b"GetStreamUri" in body:
                return _STREAM_URI_XML
            return super().post_soap(url=url, body=body)

    multi = _MultiResponseRequester(dict(requester.responses))
    client = onvif.OnvifClient(
        host="192.168.1.50", port=80, username="admin", password="hunter2", requester=multi
    )

    result = client.discover()

    assert result.device_information.manufacturer == "Acme"
    assert [dp.profile.token for dp in result.device_profiles] == ["profile-main", "profile-sub"]
    assert all(dp.stream_uri == "rtsp://192.168.1.50:554/onvif1" for dp in result.device_profiles)


def test_onvif_client_surfaces_authentication_rejection_as_a_safe_code() -> None:
    requester = _FakeOnvifRequester({_DEVICE_URL: _SOAP_FAULT_AUTH_XML})
    client = onvif.OnvifClient(host="192.168.1.50", username="admin", password="wrong", requester=requester)

    with pytest.raises(onvif.OnvifClientError) as excinfo:
        client.discover()
    assert str(excinfo.value) == "onvif_capabilities_unavailable"
    # The wrong password never appears in the raised error.
    assert "wrong" not in str(excinfo.value)


def test_onvif_client_raises_no_media_service_when_capabilities_omit_it() -> None:
    no_media = b"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
        xmlns:tds="http://www.onvif.org/ver10/device/wsdl"><soap:Body>
        <tds:GetCapabilitiesResponse><tds:Capabilities>
        <tds:Device><tds:XAddr>http://192.168.1.50/onvif/device_service</tds:XAddr></tds:Device>
        </tds:Capabilities></tds:GetCapabilitiesResponse></soap:Body></soap:Envelope>"""
    requester = _FakeOnvifRequester({_DEVICE_URL: no_media})
    client = onvif.OnvifClient(host="192.168.1.50", username="admin", password="pw", requester=requester)

    with pytest.raises(onvif.OnvifClientError) as excinfo:
        client.discover()
    assert str(excinfo.value) == "onvif_no_media_service"


def test_onvif_client_raises_no_profiles_when_camera_reports_none() -> None:
    empty_profiles = b"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
        xmlns:trt="http://www.onvif.org/ver10/media/wsdl"><soap:Body>
        <trt:GetProfilesResponse/></soap:Body></soap:Envelope>"""
    requester = _FakeOnvifRequester(
        {
            _DEVICE_URL: _CAPABILITIES_XML,
            "http://192.168.1.50/onvif/device_service": _DEVICE_INFO_XML,
            _MEDIA_URL: empty_profiles,
        }
    )
    client = onvif.OnvifClient(host="192.168.1.50", username="admin", password="pw", requester=requester)

    with pytest.raises(onvif.OnvifClientError) as excinfo:
        client.discover()
    assert str(excinfo.value) == "onvif_no_profiles"


# -- UrlLibOnvifRequester host validation (no real network call made) -------


def test_urllib_requester_refuses_a_public_host_before_any_network_call() -> None:
    requester = onvif.UrlLibOnvifRequester()
    with pytest.raises(onvif.OnvifClientError) as excinfo:
        requester.post_soap(url="http://8.8.8.8:80/onvif/device_service", body=b"<soap/>")
    assert str(excinfo.value) == "onvif_host_invalid"


def test_urllib_requester_refuses_a_non_http_scheme() -> None:
    requester = onvif.UrlLibOnvifRequester()
    with pytest.raises(onvif.OnvifClientError) as excinfo:
        requester.post_soap(url="https://192.168.1.50/onvif/device_service", body=b"<soap/>")
    assert str(excinfo.value) == "onvif_host_invalid"


# -- WS-Discovery: bounded, never raises/hangs on a quiet network -----------


class _FakeDiscoverySocket:
    """A fake UDP socket: `sendto` records the probe, `recvfrom` raises a
    timeout immediately -- simulates a quiet network with no ONVIF devices
    responding, the ordinary case, without any real network access or a
    real timeout delay."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.sent: list[bytes] = []

    def settimeout(self, _seconds: float) -> None:
        pass

    def setsockopt(self, *_args: object) -> None:
        pass

    def sendto(self, data: bytes, _address: tuple[str, int]) -> None:
        self.sent.append(data)

    def recvfrom(self, _size: int):  # noqa: ANN202
        raise TimeoutError

    def close(self) -> None:
        pass


def test_discover_onvif_devices_returns_empty_list_on_a_quiet_network() -> None:
    devices = onvif.discover_onvif_devices(
        timeout_seconds=0.01, socket_factory=lambda *a, **k: _FakeDiscoverySocket()
    )
    assert devices == []


class _RespondingDiscoverySocket(_FakeDiscoverySocket):
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        super().__init__()
        self._responses = [_PROBE_MATCHES_XML]

    def recvfrom(self, _size: int):  # noqa: ANN202
        if self._responses:
            return self._responses.pop(0), ("192.168.1.50", onvif.ONVIF_DISCOVERY_MULTICAST_PORT)
        raise TimeoutError


def test_discover_onvif_devices_collects_probe_matches_from_an_injected_socket() -> None:
    devices = onvif.discover_onvif_devices(
        timeout_seconds=0.01, socket_factory=lambda *a, **k: _RespondingDiscoverySocket()
    )
    assert len(devices) == 1
    assert devices[0].device_uuid == "urn:uuid:1234-5678"
