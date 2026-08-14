from __future__ import annotations

import os
from pathlib import Path

from microdata_lab.config import (
    SourceConfig,
    initialize_data_root,
    load_source_registry,
    resolve_data_root,
)


def test_explicit_data_root_wins(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MICRODATA_ROOT", "/ignored")
    assert resolve_data_root(tmp_path) == tmp_path.resolve()


def test_environment_data_root(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MICRODATA_ROOT", str(tmp_path))
    assert resolve_data_root() == tmp_path.resolve()


def test_protected_environment_data_root_is_loaded(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    data_root = tmp_path / "lake"
    env_file = tmp_path / ".env"
    env_file.write_text(f"MICRODATA_ROOT={data_root}\nIPUMS_API_KEY=fixture-secret\n")
    monkeypatch.delenv("MICRODATA_ROOT", raising=False)
    monkeypatch.delenv("IPUMS_API_KEY", raising=False)
    monkeypatch.setenv("MICRODATA_ENV_FILE", str(env_file))

    assert resolve_data_root() == data_root.resolve()
    assert "IPUMS_API_KEY" not in os.environ


def test_source_registry_is_typed() -> None:
    registry = load_source_registry()

    assert isinstance(registry["scf"], SourceConfig)
    assert registry["scf"].implemented is True
    assert registry["acs_pums"].credential == "IPUMS_API_KEY"


def test_initialize_data_root_creates_processing_and_lock_directories(tmp_path: Path) -> None:
    initialize_data_root(tmp_path)

    assert (tmp_path / "derived").is_dir()
    assert (tmp_path / "locks").is_dir()
