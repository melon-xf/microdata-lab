from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.fred import FredAdapter, FredConfig
from microdata_lab.models import StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)
DATA_JSON = "data_json"

_FRED_PAYLOAD = {
    "realtime_start": "2026-08-02",
    "realtime_end": "2026-08-02",
    "observation_start": "2025-01-01",
    "observation_end": "2025-12-31",
    "observations": [
        {
            "realtime_start": "2026-08-02",
            "realtime_end": "2026-08-02",
            "date": "2025-10-01",
            "value": "24055.749",
        },
        {
            "realtime_start": "2026-08-02",
            "realtime_end": "2026-08-02",
            "date": "2025-07-01",
            "value": "24026.834",
        },
        {
            "realtime_start": "2026-08-02",
            "realtime_end": "2026-08-02",
            "date": "2025-04-01",
            "value": "23950.1",
        },
    ],
}


def _adapter(tmp_path: Path) -> FredAdapter:
    cfg = FredConfig.model_validate(
        {
            "series_id": "GDPC1",
            "series_title": "Real Gross Domestic Product",
            "series_url": "https://fred.stlouisfed.org/series/GDPC1",
            "landing_page": "https://fred.stlouisfed.org/",
            "reference_year": 2025,
            "benchmark": {
                "period": "2025-10-01",
                "expected_value": 24055.749,
                "tolerance": 0.001,
            },
            "terms": "fred_open_terms",
            "record_unit": "quarterly_observation",
            "credential": "FRED_API_KEY",
        }
    )
    return FredAdapter(definition=cfg, api_key="test-key")


def _make_release(tmp_path: Path, payload: dict | None = None) -> tuple[Path, list[StoredArtifact]]:
    run_root = tmp_path / "run"
    payload = payload or _FRED_PAYLOAD
    rel = "artifacts/data_json/fred_GDPC1_2025.json"
    (run_root / rel).parent.mkdir(parents=True, exist_ok=True)
    (run_root / rel).write_text(json.dumps(payload))
    artifacts = [
        StoredArtifact(
            role=DATA_JSON,
            source_url=_url_adapter.validate_python(
                "https://api.stlouisfed.org/fred/series/observations?series_id=GDPC1"
            ),
            filename="fred_GDPC1_2025.json",
            relative_path=rel,
            sha256="0" * 64,
            bytes=len(json.dumps(payload)),
        )
    ]
    return run_root, artifacts


def test_fred_discover(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        release = adapter.discover()
        assert release.survey == "fred"
        assert release.year == 2025
        assert len(release.artifacts) == 1
        assert "api_key=test-key" in str(release.artifacts[0].url)
    finally:
        adapter.close()


def test_fred_validate_benchmark_passes(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is True
        assert result.checks["fred_benchmark"] is True
    finally:
        adapter.close()


def test_fred_validate_fails_on_error(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        payload = {"error_code": 400, "error_message": "Bad Request"}
        run_root, artifacts = _make_release(tmp_path, payload)
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is False
        assert result.checks["fred_request_succeeded"] is False
    finally:
        adapter.close()


def test_fred_normalize_writes_parquet(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        paths = adapter.normalize_release(run_root, release, artifacts)
        assert len(paths) == 1
        pf = pq.ParquetFile(paths[0])
        assert pf.metadata.num_rows == 3
    finally:
        adapter.close()
