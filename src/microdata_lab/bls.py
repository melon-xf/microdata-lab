from __future__ import annotations

import re
from typing import Final

import httpx

from microdata_lab.secrets import require_secret

_BLS_HOST: Final = "bls.gov"
_BLS_USER_AGENT = re.compile(r"^Microdata Lab/0\.1 \([^;\r\n]+; [^\s@]+@[^\s@]+\.[^\s@]+\)$")


class BLSAccessError(RuntimeError):
    """Raised when BLS returns its automated-access denial page."""


class _BLSHostOnlyTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport) -> None:
        self._inner = inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        hostname = (request.url.host or "").lower()
        if hostname != _BLS_HOST and not hostname.endswith(f".{_BLS_HOST}"):
            raise httpx.RequestError(
                f"The identified BLS client refuses non-BLS host {hostname!r}",
                request=request,
            )
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def build_bls_client(*, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Build a BLS-only client using the protected identifying User-Agent."""
    user_agent = require_secret("BLS_USER_AGENT")
    if not _BLS_USER_AGENT.fullmatch(user_agent):
        raise ValueError(
            "BLS_USER_AGENT has an invalid shape; rerun scripts/configure_bls_contact.py"
        )
    restricted_transport = _BLSHostOnlyTransport(transport or httpx.HTTPTransport(retries=3))
    return httpx.Client(
        headers={"User-Agent": user_agent},
        follow_redirects=True,
        timeout=httpx.Timeout(connect=30.0, read=180.0, write=60.0, pool=30.0),
        transport=restricted_transport,
    )


def require_bls_response(response: httpx.Response) -> httpx.Response:
    """Reject HTTP failures and BLS denial pages that sometimes return as HTML."""
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "html" in content_type:
        normalized = response.text.lower()
        if "access denied" in normalized and "bls" in normalized:
            raise BLSAccessError("BLS rejected the identified automated request")
    return response
