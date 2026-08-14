from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.census import CensusAdapter, CensusConfig
from microdata_lab.models import StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)
DATA_JSON = "data_json"

_CENSUS_PAYLOAD = [
    ["B01001_001E", "us"],
    ["334914895", "1"],
]


def _adapter(tmp_path: Path) -> CensusAdapter:
    cfg = CensusConfig.model_validate(
        {
            "dataset": "acs/acs1",
            "dataset_title": "American Community Survey 1-Year Estimates",
            "variables": ["B01001_001E"],
            "landing_page": "https://www.census.gov/data/developers/data-sets/acs-1year.html",
            "reference_year": 2023,
            "benchmark": {
                "variable": "B01001_001E",
                "geo": "us",
                "expected_value": None,
                "tolerance": 0.001,
            },
            "terms": "census_public_domain",
            "record_unit": "table_estimate",
            "credential": "CENSUS_API_KEY",
        }
    )
    return CensusAdapter(definition=cfg, api_key="test-key")


def _make_release(tmp_path: Path, payload: list | None = None) -> tuple[Path, list[StoredArtifact]]:
    run_root = tmp_path / "run"
    if payload is None:
        payload = _CENSUS_PAYLOAD
    rel = "artifacts/data_json/census_acs_acs1_2023.json"
    (run_root / rel).parent.mkdir(parents=True, exist_ok=True)
    (run_root / rel).write_text(json.dumps(payload))
    artifacts = [
        StoredArtifact(
            role=DATA_JSON,
            source_url=_url_adapter.validate_python(
                "https://api.census.gov/data/2023/acs/acs1?get=B01001_001E&for=us:1"
            ),
            filename="census_acs_acs1_2023.json",
            relative_path=rel,
            sha256="0" * 64,
            bytes=len(json.dumps(payload)),
        )
    ]
    return run_root, artifacts


def test_census_discover(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        release = adapter.discover()
        assert release.survey == "census"
        assert release.year == 2023
        assert len(release.artifacts) == 1
        assert "key=test-key" in str(release.artifacts[0].url)
    finally:
        adapter.close()


def test_census_validate_benchmark_passes(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is True
        assert result.checks["census_benchmark"] is True
    finally:
        adapter.close()


def test_census_validate_fails_on_missing_rows(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path, [])
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is False
    finally:
        adapter.close()


def test_census_normalize_writes_parquet(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        paths = adapter.normalize_release(run_root, release, artifacts)
        assert len(paths) == 1
        pf = pq.ParquetFile(paths[0])
        assert pf.metadata.num_rows == 1
    finally:
        adapter.close()
