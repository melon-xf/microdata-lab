from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.worldbank import WorldBankAdapter
from microdata_lab.models import DiscoveredRelease, StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)
DATA_JSON = "data_json"


def _config(tmp_path: Path) -> None:
    config_dir = tmp_path / "config/worldbank"
    config_dir.mkdir(parents=True)
    (config_dir / "gdp.yaml").write_text(
        """indicator: NY.GDP.MKTP.CD
indicator_title: GDP (current US$)
indicator_url: https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD
landing_page: https://data.worldbank.org/indicator/NY.GDP.MKTP.CD
reference_year: 2023
benchmark:
  country: USA
  expected_value: null
  tolerance: 0.01
terms: cc_by_4_0
"""
    )


def _adapter(tmp_path: Path) -> WorldBankAdapter:

    from microdata_lab.adapters.worldbank import WorldBankConfig

    cfg = WorldBankConfig.model_validate(
        {
            "indicator": "NY.GDP.MKTP.CD",
            "indicator_title": "GDP (current US$)",
            "indicator_url": "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD",
            "landing_page": "https://data.worldbank.org/indicator/NY.GDP.MKTP.CD",
            "reference_year": 2023,
            "benchmark": {"country": "USA", "expected_value": None, "tolerance": 0.01},
            "terms": "cc_by_4_0",
        }
    )
    return WorldBankAdapter(definition=cfg)


def _make_release(year: int = 2023) -> DiscoveredRelease:
    return DiscoveredRelease(
        survey="worldbank",
        year=year,
        landing_page=_url_adapter.validate_python(
            "https://data.worldbank.org/indicator/NY.GDP.MKTP.CD"
        ),
        artifacts=[],
    )


def _wb_response() -> list[Any]:
    return [
        {"page": 1, "pages": 1, "per_page": 1000, "total": 3},
        [
            {
                "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                "country": {"id": "US", "value": "United States"},
                "countryiso3code": "USA",
                "date": "2023",
                "value": 27360900000000.0,
                "unit": "",
                "obs_status": "",
                "decimal": 0,
            },
            {
                "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                "country": {"id": "CN", "value": "China"},
                "countryiso3code": "CHN",
                "date": "2023",
                "value": 17794700000000.0,
                "unit": "",
                "obs_status": "",
                "decimal": 0,
            },
            {
                "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                "country": {"id": "JP", "value": "Japan"},
                "countryiso3code": "JPN",
                "date": "2023",
                "value": 4212940000000.0,
                "unit": "",
                "obs_status": "",
                "decimal": 0,
            },
        ],
    ]


def _store_artifact(tmp_path: Path, response: list[Any]) -> list[StoredArtifact]:
    art_dir = tmp_path / "artifacts/data_json"
    art_dir.mkdir(parents=True, exist_ok=True)
    fname = "wb_NY.GDP.MKTP.CD_2023.json"
    (art_dir / fname).write_text(json.dumps(response))
    return [
        StoredArtifact(
            role=DATA_JSON,
            source_url=_url_adapter.validate_python(
                "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&date=2023&per_page=1000"
            ),
            filename=fname,
            relative_path=f"artifacts/data_json/{fname}",
            sha256="0" * 64,
            bytes=len(json.dumps(response)),
        )
    ]


def test_wb_discover(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    release = adapter.discover()
    assert release.survey == "worldbank"
    assert release.year == 2023
    assert len(release.artifacts) == 1
    assert str(release.artifacts[0].role) == DATA_JSON
    adapter.close()


def test_wb_validate_passes(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    release = _make_release()
    artifacts = _store_artifact(tmp_path, _wb_response())
    result = adapter.validate_release(tmp_path, release, artifacts)
    assert result.passed
    assert result.checks["wb_observations_present"]
    assert result.checks["wb_benchmark_observation_present"]
    adapter.close()


def test_wb_normalize_creates_parquet(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    release = _make_release()
    artifacts = _store_artifact(tmp_path, _wb_response())
    outputs = adapter.normalize_release(tmp_path, release, artifacts)
    assert len(outputs) == 1
    assert outputs[0].name == "wb_NY.GDP.MKTP.CD.parquet"
    meta = pq.ParquetFile(outputs[0]).metadata
    assert meta.num_rows == 3
    adapter.close()


def test_wb_redistribution_note_in_metadata(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    release = adapter.discover()
    assert "redistribution_note" in release.source_metadata
    assert "CC BY 4.0" in release.source_metadata["redistribution_note"]
    adapter.close()
