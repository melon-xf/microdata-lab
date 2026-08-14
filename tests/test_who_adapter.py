from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.who import WhoAdapter, WhoConfig
from microdata_lab.models import StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)
DATA_JSON = "data_json"


def _config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config/who"
    config_dir.mkdir(parents=True)
    p = config_dir / "life-expectancy.yaml"
    p.write_text(
        """indicator_code: WHOSIS_000001
indicator_title: Life expectancy at birth (years)
indicator_url: https://www.who.int/data/gho/data/indicators/indicator-details/GHO/life-expectancy-at-birth-(years)
landing_page: https://www.who.int/data/gho
reference_year: 2021
benchmark:
  country: USA
  sex: SEX_BTSX
  expected_value: 76.37
  tolerance: 0.01
terms: cc_by_4_0
record_unit: country_year_observation
"""
    )
    return p


def _adapter(tmp_path: Path) -> WhoAdapter:
    cfg = WhoConfig.model_validate(
        {
            "indicator_code": "WHOSIS_000001",
            "indicator_title": "Life expectancy at birth (years)",
            "indicator_url": "https://www.who.int/data/gho/data/indicators/indicator-details/GHO/life-expectancy-at-birth-(years)",
            "landing_page": "https://www.who.int/data/gho",
            "reference_year": 2021,
            "benchmark": {
                "country": "USA",
                "sex": "SEX_BTSX",
                "expected_value": 76.37,
                "tolerance": 0.01,
            },
            "terms": "cc_by_4_0",
            "record_unit": "country_year_observation",
        }
    )
    return WhoAdapter(definition=cfg)


def _make_release(tmp_path: Path) -> tuple[Path, list[StoredArtifact]]:
    run_root = tmp_path / "run"
    (run_root / "artifacts" / DATA_JSON).mkdir(parents=True)
    payload = {
        "value": [
            {
                "SpatialDim": "USA",
                "TimeDim": 2021,
                "Dim1": "SEX_BTSX",
                "NumericValue": 76.37368104,
            },
            {"SpatialDim": "USA", "TimeDim": 2021, "Dim1": "SEX_MLE", "NumericValue": 73.5},
            {"SpatialDim": "FRA", "TimeDim": 2021, "Dim1": "SEX_BTSX", "NumericValue": 82.2},
        ]
    }
    rel = "artifacts/data_json/who_WHOSIS_000001_2021.json"
    (run_root / rel).parent.mkdir(parents=True, exist_ok=True)
    (run_root / rel).write_text(json.dumps(payload))
    artifacts = [
        StoredArtifact(
            role=DATA_JSON,
            source_url=_url_adapter.validate_python(
                "https://ghoapi.azureedge.net/api/WHOSIS_000001"
            ),
            filename="who_WHOSIS_000001_2021.json",
            relative_path=rel,
            sha256="0" * 64,
            bytes=len(json.dumps(payload)),
        )
    ]
    return run_root, artifacts


def test_who_discover(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        release = adapter.discover()
        assert release.survey == "who"
        assert release.year == 2021
        assert len(release.artifacts) == 1
        assert str(release.artifacts[0].role) == DATA_JSON
    finally:
        adapter.close()


def test_who_validate_benchmark_passes(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is True
        assert result.checks["who_benchmark"] is True
    finally:
        adapter.close()


def test_who_validate_fails_on_wrong_value(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        # Corrupt the benchmark value
        p = run_root / artifacts[0].relative_path
        payload = json.loads(p.read_text())
        payload["value"][0]["NumericValue"] = 60.0
        p.write_text(json.dumps(payload))
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is False
        assert result.checks["who_benchmark"] is False
    finally:
        adapter.close()


def test_who_normalize_writes_parquet(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        paths = adapter.normalize_release(run_root, release, artifacts)
        assert len(paths) == 1
        pf = pq.ParquetFile(paths[0])
        assert pf.metadata.num_rows == 3
        assert pf.metadata.num_columns == 7
    finally:
        adapter.close()
