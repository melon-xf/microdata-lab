from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from microdata_lab.catalog import _connect_with_lock_retry, rebuild_catalog
from microdata_lab.config import initialize_data_root


def test_rebuild_catalog_is_rebuildable(tmp_path: Path) -> None:
    initialize_data_root(tmp_path)
    (tmp_path / "current").mkdir(exist_ok=True)
    # No releases: rebuild must succeed and report zeros.
    counts = rebuild_catalog(tmp_path)
    assert counts.releases == 0
    assert counts.variables == 0
    assert counts.documents == 0
    # And be idempotent.
    counts2 = rebuild_catalog(tmp_path)
    assert counts2.releases == 0


def test_connect_with_lock_retry_retries_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_data_root(tmp_path)
    database = tmp_path / "catalog" / "catalog.duckdb"
    real_connect = duckdb.connect
    calls = {"n": 0}

    def flaky_connect(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise duckdb.IOException("Could not set lock on file ... Conflicting lock")
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", flaky_connect)
    connection = _connect_with_lock_retry(database)
    try:
        connection.execute("SELECT 1")
    finally:
        connection.close()
    assert calls["n"] == 3


def test_connect_with_lock_retry_gives_up_after_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_data_root(tmp_path)
    database = tmp_path / "catalog" / "catalog.duckdb"

    def always_locked(*args, **kwargs):
        raise duckdb.IOException("Conflicting lock is held")

    monkeypatch.setattr(duckdb, "connect", always_locked)
    with pytest.raises(duckdb.IOException):
        _connect_with_lock_retry(database)
