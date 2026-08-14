from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.eurostat import EurostatAdapter
from microdata_lab.models import StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)


def _make_synthetic_payload() -> dict:
    """Create a small Eurostat-format JSON payload with 2 EU countries."""
    return {
        "version": "1.0",
        "label": "GDP and main components",
        "href": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10_gdp",
        "dimension": {
            "freq": {"category": {"index": {"A": 0}, "label": {"A": "Annual"}}},
            "unit": {
                "category": {
                    "index": {"CP_MEUR": 0},
                    "label": {"CP_MEUR": "Current prices, million euro"},
                }
            },
            "na_item": {
                "category": {
                    "index": {"B1GQ": 0},
                    "label": {"B1GQ": "Gross domestic product at market prices"},
                }
            },
            "geo": {
                "category": {
                    "index": {"DE": 0, "FR": 1},
                    "label": {"DE": "Germany", "FR": "France"},
                }
            },
            "time": {"category": {"index": {"2023": 0}, "label": {"2023": "2023"}}},
        },
        "size": [1, 1, 1, 2, 1],
        "value": {"0": 4219310.0, "1": 2630000.0},
    }


def _store_artifacts(tmp_path: Path, payload: dict) -> list[StoredArtifact]:
    json_path = tmp_path / "artifacts" / "data_json"
    json_path.mkdir(parents=True, exist_ok=True)
    json_file = json_path / "nama_10_gdp_2023.json"
    with json_file.open("w") as f:
        json.dump(payload, f)
    return [
        StoredArtifact(
            role="data_json",
            source_url=_url_adapter.validate_strings(
                "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10_gdp"
            ),
            filename="nama_10_gdp_2023.json",
            relative_path="artifacts/data_json/nama_10_gdp_2023.json",
            sha256="0" * 64,
            bytes=json_file.stat().st_size,
        ),
    ]


def _adapter() -> EurostatAdapter:
    return EurostatAdapter()


def test_eurostat_discover() -> None:
    adapter = _adapter()
    release = adapter.discover(2023)
    assert release.survey == "eurostat"
    assert release.year == 2023
    assert len(release.artifacts) == 1
    assert str(release.artifacts[0].role) == "data_json"
    adapter.close()


def test_eurostat_validate_passes(tmp_path: Path) -> None:
    adapter = _adapter()
    release = adapter.discover(2023)
    artifacts = _store_artifacts(tmp_path, _make_synthetic_payload())
    result = adapter.validate_release(tmp_path, release, artifacts)
    assert result.passed, f"Failed: {result.checks}, notes: {result.notes}"
    assert result.checks["eurostat_json_present"]
    assert result.checks["eurostat_observations_present"]
    assert result.checks["eurostat_benchmark_value_matches"]
    adapter.close()


def test_eurostat_validate_rejects_wrong_benchmark(tmp_path: Path) -> None:
    adapter = _adapter()
    release = adapter.discover(2023)
    payload = _make_synthetic_payload()
    payload["value"]["0"] = 999999.0  # Wrong DE value
    artifacts = _store_artifacts(tmp_path, payload)
    result = adapter.validate_release(tmp_path, release, artifacts)
    assert not result.passed
    assert not result.checks["eurostat_benchmark_value_matches"]
    adapter.close()


def test_eurostat_normalize(tmp_path: Path) -> None:
    adapter = _adapter()
    release = adapter.discover(2023)
    artifacts = _store_artifacts(tmp_path, _make_synthetic_payload())
    outputs = adapter.normalize_release(tmp_path, release, artifacts)
    assert len(outputs) == 1
    assert outputs[0].name == "nama_10_gdp.parquet"
    meta = pq.ParquetFile(outputs[0]).metadata
    assert meta.num_rows == 2
    adapter.close()
