"""Conservative PDF download for tender attachment URLs.

Only public http(s) hosts are allowed, redirects are re-validated, and the
response must be an actual PDF. Failures carry a reason so the UI can ask the
user to upload the file instead of pretending extraction succeeded.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

USER_AGENT = "BidKaro/0.1 (tender document collection; contact: local-demo)"
MAX_REDIRECTS = 4


class DownloadError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DownloadError("invalid_url", "Only public http(s) URLs can be fetched.")

    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, None)}
    except socket.gaierror as exc:
        raise DownloadError("dns_failed", "The host could not be resolved.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise DownloadError(
                "private_host", "The URL resolves to a private or reserved address."
            )


def download_pdf(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: int = 30,
) -> tuple[bytes, str, str]:
    """Return (content, final_url, content_type) or raise DownloadError."""
    current = url.strip()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*;q=0.8"}

    for _ in range(MAX_REDIRECTS + 1):
        _validate_public_url(current)
        try:
            with httpx.Client(
                follow_redirects=False,
                timeout=timeout_seconds,
                headers=headers,
            ) as client:
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise DownloadError("redirect_failed", "The server sent an empty redirect.")
                        current = urljoin(current, location)
                        continue

                    if response.status_code in {401, 403}:
                        raise DownloadError(
                            "http_403",
                            "The portal refused the automated request (login or bot protection).",
                        )
                    if response.status_code == 404:
                        raise DownloadError("http_404", "The attachment URL was not found.")
                    if response.status_code >= 400:
                        raise DownloadError(
                            "http_error", f"The server returned HTTP {response.status_code}."
                        )

                    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    buffer = bytearray()
                    for chunk in response.iter_bytes():
                        buffer.extend(chunk)
                        if len(buffer) > max_bytes:
                            raise DownloadError(
                                "too_large", "The attachment is larger than the upload limit."
                            )

                    if not bytes(buffer).startswith(b"%PDF-"):
                        raise DownloadError(
                            "not_pdf",
                            "The URL did not return a PDF (likely a login or error page).",
                        )
                    return bytes(buffer), str(response.url), content_type or "application/pdf"
        except httpx.TimeoutException as exc:
            raise DownloadError("timeout", "The download timed out.") from exc
        except httpx.HTTPError as exc:
            raise DownloadError("network_error", "The download failed.") from exc

    raise DownloadError("too_many_redirects", "The attachment redirected too many times.")
