"""Bounded external URL still-image preview helper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import base64
import ipaddress
import socket
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import urllib.request

PreviewStatus = Literal["available", "not_configured", "unavailable", "unsupported", "error"]

DEFAULT_TIMEOUT_SECONDS = 3.0
MIN_TIMEOUT_SECONDS = 0.5
MAX_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_BYTES = 5_000_000
MAX_MAX_BYTES = 10_000_000
SUPPORTED_STILL_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
USER_AGENT = "MockingBird local preview"
METADATA_IPV4_ADDRESS = ipaddress.ip_address("169.254.169.254")


@dataclass(frozen=True)
class ExternalUrlPreviewFetchResult:
    status: PreviewStatus
    message: str
    fetched_at: datetime | None = None
    content_type: str | None = None
    content_length: int | None = None
    bytes_read: int | None = None
    preview_data_url: str | None = None
    warnings: list[str] = field(default_factory=list)


class ExternalUrlUnsupported(ValueError):
    pass


class ExternalUrlUnavailable(ValueError):
    pass


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def fetch_external_url_preview(
    url: str,
    *,
    timeout_seconds: float | None = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int | None = DEFAULT_MAX_BYTES,
) -> ExternalUrlPreviewFetchResult:
    timeout = _clamp_timeout(timeout_seconds)
    byte_limit = _clamp_max_bytes(max_bytes)

    try:
        _validate_external_url(url)
    except ExternalUrlUnsupported as error:
        return ExternalUrlPreviewFetchResult(status="unsupported", message=str(error))
    except ExternalUrlUnavailable as error:
        return ExternalUrlPreviewFetchResult(status="unavailable", message=str(error))

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "image/jpeg,image/png,image/webp"},
        method="GET",
    )

    try:
        with _build_no_redirect_opener().open(request, timeout=timeout) as response:
            content_type = _normalize_content_type(response.headers.get("Content-Type"))
            if content_type not in SUPPORTED_STILL_IMAGE_CONTENT_TYPES:
                return ExternalUrlPreviewFetchResult(
                    status="unsupported",
                    message="External URL preview supports JPEG, PNG, and WebP still images only.",
                    content_type=content_type,
                )

            content_length = _parse_content_length(response.headers.get("Content-Length"))
            if content_length is not None and content_length > byte_limit:
                return ExternalUrlPreviewFetchResult(
                    status="unsupported",
                    message="External URL preview response exceeds the configured byte limit.",
                    content_type=content_type,
                    content_length=content_length,
                )

            body = response.read(byte_limit + 1)
            if len(body) > byte_limit:
                return ExternalUrlPreviewFetchResult(
                    status="unsupported",
                    message="External URL preview response exceeds the configured byte limit.",
                    content_type=content_type,
                    content_length=content_length,
                    bytes_read=len(body),
                )

            preview = base64.b64encode(body).decode("ascii")
            return ExternalUrlPreviewFetchResult(
                status="available",
                message="Still-image preview fetched explicitly. It was not saved and created no truth.",
                fetched_at=datetime.now(UTC),
                content_type=content_type,
                content_length=content_length,
                bytes_read=len(body),
                preview_data_url=f"data:{content_type};base64,{preview}",
            )
    except HTTPError as error:
        if 300 <= error.code < 400:
            return ExternalUrlPreviewFetchResult(
                status="unsupported",
                message="Redirects are not supported for external URL preview in this phase.",
            )
        return ExternalUrlPreviewFetchResult(
            status="unavailable",
            message="External URL preview request returned an unavailable HTTP status.",
        )
    except (TimeoutError, socket.timeout, URLError):
        return ExternalUrlPreviewFetchResult(
            status="unavailable",
            message="External URL preview request failed or timed out.",
        )
    except Exception:
        return ExternalUrlPreviewFetchResult(
            status="error",
            message="External URL preview failed safely.",
        )


def _validate_external_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ExternalUrlUnsupported("External URL preview supports http and https URLs only.")
    if not parsed.hostname:
        raise ExternalUrlUnsupported("External URL preview requires a hostname.")
    if parsed.username or parsed.password:
        raise ExternalUrlUnsupported("Credentials in URLs are not supported for preview.")
    if parsed.fragment:
        raise ExternalUrlUnsupported("URL fragments are not supported for preview.")

    # Local-first means RFC1918 LAN camera URLs are allowed, but metadata,
    # loopback, multicast, unspecified, reserved, and link-local targets fail closed.
    for address in _resolve_host_addresses(parsed.hostname):
        _validate_resolved_address(address)


def _validate_resolved_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if address == METADATA_IPV4_ADDRESS:
        raise ExternalUrlUnsupported("Link-local metadata targets are not supported for preview.")
    if (
        address.is_loopback
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        or address.is_link_local
    ):
        raise ExternalUrlUnsupported("Unsafe URL target is not supported for preview.")


def _resolve_host_addresses(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ExternalUrlUnavailable("External URL hostname could not be resolved.") from error

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        addresses.append(ipaddress.ip_address(sockaddr[0]))
    return addresses


def _build_no_redirect_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirectHandler)


def _clamp_timeout(value: float | None) -> float:
    timeout = DEFAULT_TIMEOUT_SECONDS if value is None else float(value)
    return min(max(timeout, MIN_TIMEOUT_SECONDS), MAX_TIMEOUT_SECONDS)


def _clamp_max_bytes(value: int | None) -> int:
    byte_limit = DEFAULT_MAX_BYTES if value is None else int(value)
    return min(max(byte_limit, 1), MAX_MAX_BYTES)


def _normalize_content_type(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower()


def _parse_content_length(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
