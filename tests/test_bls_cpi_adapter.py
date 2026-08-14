from __future__ import annotations

import json
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.bls_cpi import BlsAdapter, BlsConfig
from microdata_lab.models import StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)
DATA_JSON = "data_json"

_CPI_PAYLOAD = {
    "status": "REQUEST_SUCCEEDED",
    "responseTime": 123,
    "message": [],
    "Results": {
        "series": [
            {
                "seriesID": "CUUR0000SA0",
                "data": [
                    {
                        "year": "2024",
                        "period": "M12",
                        "periodName": "December",
                        "value": "315.605",
                        "footnotes": [{"text": ""}],
                    },
                    {
                        "year": "2024",
                        "period": "M11",
                        "periodName": "November",
                        "value": "315.493",
                        "footnotes": [{"text": ""}],
                    },
                    {
                        "year": "2024",
                        "period": "M01",
                        "periodName": "January",
                        "value": "308.417",
                        "footnotes": [{"text": ""}],
                    },
                ],
            }
        ],
    },
}


def _adapter(tmp_path: Path) -> BlsAdapter:
    cfg = BlsConfig.model_validate(
        {
            "series_id": "CUUR0000SA0",
            "series_title": "CPI-U All items (seasonally adjusted)",
            "series_url": "https://data.bls.gov/timeseries/CUUR0000SA0",
            "landing_page": "https://www.bls.gov/cpi/",
            "reference_year": 2024,
            "benchmark": {"period": "2024-12", "expected_value": 315.605, "tolerance": 0.001},
            "terms": "us_federal_public_domain",
            "record_unit": "monthly_index_observation",
        }
    )
    return BlsAdapter(definition=cfg)


def _make_release(tmp_path: Path, payload: dict | None = None) -> tuple[Path, list[StoredArtifact]]:
    run_root = tmp_path / "run"
    payload = payload or _CPI_PAYLOAD
    rel = "artifacts/data_json/bls_CUUR0000SA0_2024.json"
    (run_root / rel).parent.mkdir(parents=True, exist_ok=True)
    (run_root / rel).write_text(json.dumps(payload))
    artifacts = [
        StoredArtifact(
            role=DATA_JSON,
            source_url=_url_adapter.validate_python(
                "https://api.bls.gov/publicAPI/v2/timeseries/data/"
            ),
            filename="bls_CUUR0000SA0_2024.json",
            relative_path=rel,
            sha256="0" * 64,
            bytes=len(json.dumps(payload)),
        )
    ]
    return run_root, artifacts


def test_bls_discover_has_payload(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        release = adapter.discover()
        assert release.survey == "bls_cpi"
        assert release.year == 2024
        assert len(release.artifacts) == 1
        art = release.artifacts[0]
        assert art.request_payload is not None
        assert art.request_payload["seriesid"] == ["CUUR0000SA0"]
        assert art.request_payload["startyear"] == "2024"
    finally:
        adapter.close()


def test_bls_validate_benchmark_passes(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is True
        assert result.checks["bls_benchmark"] is True
        assert result.checks["bls_request_succeeded"] is True
    finally:
        adapter.close()


def test_bls_validate_fails_on_wrong_value(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        payload = json.loads(json.dumps(_CPI_PAYLOAD))
        payload["Results"]["series"][0]["data"][0]["value"] = "999.0"
        run_root, artifacts = _make_release(tmp_path, payload)
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is False
        assert result.checks["bls_benchmark"] is False
    finally:
        adapter.close()


def test_bls_normalize_writes_parquet(tmp_path: Path) -> None:
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


def test_bls_download_client_restricts_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The BLS client must refuse non-BLS hosts."""
    adapter = _adapter(tmp_path)
    monkeypatch.setenv("BLS_USER_AGENT", "Microdata Lab/0.1 (contributor; test@example.com)")
    try:
        client = adapter.download_client()
        with pytest.raises(httpx.RequestError):
            client.get("https://example.com/not-bls")
    finally:
        adapter.close()
