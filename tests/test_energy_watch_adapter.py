"""Tests for the keyless Hormuz energy-watch adapter."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.energy_watch import (
    EXPECTED_HORMUZ_FLOW_2024,
    SERIES,
    EnergyWatchAdapter,
)
from microdata_lab.models import StoredArtifact

_url = TypeAdapter(AnyHttpUrl)


def _artifacts(tmp_path: Path) -> tuple[Path, list[StoredArtifact]]:
    run = tmp_path / "run"
    artifacts: list[StoredArtifact] = []
    for role, meta in SERIES.items():
        series_id = str(meta["id"])
        path = run / "artifacts" / role / f"{series_id}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "observation_date": pd.date_range("2026-02-01", periods=12),
                series_id: [float(index + 1) for index in range(12)],
            }
        ).to_csv(path, index=False)
        artifacts.append(
            StoredArtifact(
                role=role,
                source_url=_url.validate_python(
                    f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
                ),
                filename=path.name,
                relative_path=str(path.relative_to(run)),
                sha256="0" * 64,
                bytes=path.stat().st_size,
            )
        )
    xlsx = run / "artifacts" / "hormuz_xlsx" / "hormuz.xlsx"
    xlsx.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            [None, "Volume of crude oil transported through the Strait of Hormuz"],
            [None, None, 2023, 2024, "1Q25"],
            [
                None,
                "Total oil flows through Strait of Hormuz",
                21.388755284931506,
                EXPECTED_HORMUZ_FLOW_2024,
                20.103206311111112,
            ],
        ]
    ).to_excel(xlsx, sheet_name="CrudeAndProducts", header=False, index=False)
    artifacts.append(
        StoredArtifact(
            role="hormuz_xlsx",
            source_url=_url.validate_python("https://www.eia.gov/example.xlsx"),
            filename=xlsx.name,
            relative_path=str(xlsx.relative_to(run)),
            sha256="0" * 64,
            bytes=xlsx.stat().st_size,
        )
    )
    return run, artifacts


def test_energy_watch_discovery_is_keyless() -> None:
    release = EnergyWatchAdapter().discover()
    assert release.survey == "energy_watch"
    assert release.year == 2026
    assert len(release.artifacts) == 4
    assert all("api_key" not in str(artifact.url) for artifact in release.artifacts)


def test_energy_watch_rejects_other_years() -> None:
    try:
        EnergyWatchAdapter().discover(year=2025)
    except ValueError as error:
        assert "only supports 2026" in str(error)
    else:
        raise AssertionError("Expected unsupported year to fail")


def test_energy_watch_validates_and_normalizes(tmp_path: Path) -> None:
    adapter = EnergyWatchAdapter()
    release = adapter.discover()
    run, artifacts = _artifacts(tmp_path)
    validation = adapter.validate_release(run, release, artifacts)
    assert validation.passed
    assert validation.checks["hormuz_flow_benchmark"]
    outputs = adapter.normalize_release(run, release, artifacts)
    assert len(outputs) == 1
    parquet = pq.ParquetFile(outputs[0])
    assert parquet.metadata.num_rows == 37
    assert parquet.schema.names == [
        "series_id",
        "series_title",
        "date",
        "value",
        "unit",
        "frequency",
    ]
    normalized = pd.read_parquet(outputs[0])
    exposure = normalized.loc[normalized["series_id"] == "EIA_HORMUZ_TOTAL_OIL"]
    assert float(exposure.iloc[0]["value"]) == pytest.approx(EXPECTED_HORMUZ_FLOW_2024, abs=1e-12)
