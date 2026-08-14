from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


def _default_env_path() -> Path:
    """Platform-standard dotenv location: $XDG_CONFIG_HOME/microdata-lab/.env.

    Honors XDG on Linux/macOS; falls back to ~/.config/microdata-lab/.env.
    Override entirely with MICRODATA_ENV_FILE.
    """
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base).expanduser() / "microdata-lab" / ".env"
    return Path.home() / ".config" / "microdata-lab" / ".env"


def _runtime_environment_candidates() -> list[Path | None]:
    configured = os.environ.get("MICRODATA_ENV_FILE")
    if configured:
        return [Path(configured).expanduser()]
    return [
        Path.cwd() / ".env",
        _default_env_path(),
    ]


def load_runtime_environment() -> Path | None:
    """Load an excluded environment file in-process without shell expansion or output."""
    for candidate in _runtime_environment_candidates():
        if candidate is not None and candidate.is_file():
            load_dotenv(candidate, override=False)
            return candidate
    return None


def read_runtime_value(name: str) -> str | None:
    """Read one runtime value without injecting unrelated settings into the process."""
    configured = os.environ.get(name)
    if configured:
        return configured
    for candidate in _runtime_environment_candidates():
        if candidate is None or not candidate.is_file():
            continue
        value = dotenv_values(candidate, interpolate=False).get(name)
        if value:
            return value
    return None


def require_secret(name: str) -> str:
    load_runtime_environment()
    value = os.environ.get(name)
    if not value:
        setup_script = {
            "BLS_USER_AGENT": "uv run python scripts/configure_bls_contact.py",
            "CENSUS_API_KEY": "uv run python scripts/configure_api_key.py census",
            "FRED_API_KEY": "uv run python scripts/configure_api_key.py fred",
            "IPUMS_API_KEY": "uv run python scripts/configure_ipums_key.py",
        }.get(name, "the protected local configuration helper")
        raise RuntimeError(
            f"Missing required secret {name}. Run {setup_script}; "
            "never paste credentials into chat, logs, or shell history."
        )
    return value


def update_env_file(path: Path, name: str, value: str) -> None:
    """Atomically add or replace one dotenv assignment without exposing its value."""
    if not value or "\n" in value or "\r" in value:
        raise ValueError(f"{name} must be a non-empty single-line value")
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.is_file() else ""
    replacement = f"{name}={value}"
    lines = existing.splitlines()
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.lstrip().startswith(f"{name}="):
            if not replaced:
                updated.append(replacement)
                replaced = True
            continue
        updated.append(line)
    if not replaced:
        if updated and updated[-1] != "":
            updated.append("")
        updated.append(replacement)

    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write("\n".join(updated).rstrip("\n") + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)
