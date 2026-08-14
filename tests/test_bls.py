from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from microdata_lab.bls import BLSAccessError, build_bls_client, require_bls_response

_USER_AGENT = "Microdata Lab/0.1 (Example Researcher; researcher@example.org)"


def test_bls_client_sends_identifier_only_to_bls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLS_USER_AGENT", _USER_AGENT)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == _USER_AGENT
        return httpx.Response(200, request=request, text="Public use microdata")

    with build_bls_client(transport=httpx.MockTransport(handler)) as client:
        response = client.get("https://www.bls.gov/cex/pumd_data.htm")
        assert response.status_code == 200
        with pytest.raises(httpx.RequestError, match="refuses non-BLS host"):
            client.get("https://example.org/")


def test_bls_client_rejects_invalid_identifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLS_USER_AGENT", "generic-bot")

    with pytest.raises(ValueError, match="invalid shape"):
        build_bls_client()


def test_require_bls_response_rejects_denial_page() -> None:
    request = httpx.Request("GET", "https://www.bls.gov/")
    response = httpx.Response(
        200,
        request=request,
        headers={"content-type": "text/html"},
        text="BLS Access Denied",
    )

    with pytest.raises(BLSAccessError, match="rejected"):
        require_bls_response(response)


def test_require_secret_names_bls_setup_helper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BLS_USER_AGENT", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MICRODATA_ENV_FILE", "/definitely/missing")

    with pytest.raises(RuntimeError, match=r"scripts/configure_bls_contact\.py"):
        build_bls_client()
