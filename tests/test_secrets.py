from __future__ import annotations

import stat
from pathlib import Path

import pytest

from microdata_lab.secrets import require_secret, update_env_file


def test_update_env_file_preserves_other_values_and_replaces_once(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=value\nIPUMS_API_KEY=old\nIPUMS_API_KEY=duplicate\n")

    update_env_file(env_file, "IPUMS_API_KEY", "new-secret")

    content = env_file.read_text()
    assert "OTHER=value" in content
    assert content.count("IPUMS_API_KEY=") == 1
    assert "IPUMS_API_KEY=new-secret" in content
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600


def test_update_env_file_rejects_multiline_secret(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="single-line"):
        update_env_file(tmp_path / ".env", "IPUMS_API_KEY", "bad\nvalue")


def test_require_secret_fails_without_printing_or_guessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IPUMS_API_KEY", raising=False)
    monkeypatch.setenv("MICRODATA_ENV_FILE", "/definitely/missing")

    with pytest.raises(RuntimeError, match=r"scripts/configure_ipums_key\.py"):
        require_secret("IPUMS_API_KEY")


@pytest.mark.parametrize(
    ("credential", "helper"),
    [
        ("CENSUS_API_KEY", r"scripts/configure_api_key\.py census"),
        ("FRED_API_KEY", r"scripts/configure_api_key\.py fred"),
    ],
)
def test_require_secret_names_api_key_helper(
    monkeypatch: pytest.MonkeyPatch,
    credential: str,
    helper: str,
) -> None:
    monkeypatch.delenv(credential, raising=False)
    monkeypatch.setenv("MICRODATA_ENV_FILE", "/definitely/missing")

    with pytest.raises(RuntimeError, match=helper):
        require_secret(credential)
