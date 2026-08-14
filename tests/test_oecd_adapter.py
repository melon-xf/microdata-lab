from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.oecd import OECDAdapter, OECDBenchmark, OECDDatasetConfig
from microdata_lab.models import DiscoveredArtifact, DiscoveredRelease, StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)


def _config() -> OECDDatasetConfig:
    return OECDDatasetConfig(
        dataset="QNA",
        dataset_title="Quarterly National Accounts",
        dataset_url=_url_adapter.validate_python("https://stats.oecd.org/SDMX-JSON/data/QNA"),
        frequency="Q",
        landing_page=_url_adapter.validate_python(
            "https://stats.oecd.org/Index.aspx?DatasetCode=QNA"
        ),
        reference_year=2023,
        time_range={"start": "2023-Q1", "end": "2023-Q4"},
        benchmark=OECDBenchmark(
            ref_area="USA",
            transaction="B1GQ",
            transformation="GY",
            frequency="Q",
            time_period="2023-Q4",
            expected_value=2.5,
            tolerance=1.0,
        ),
    )


def _sdmx_response() -> dict[str, Any]:
    """A minimal SDMX-JSON response with two series and two observations each."""
    return {
        "meta": {"schema": "sdmx-json", "prepared": "2026-01-01T00:00:00Z"},
        "data": {
            "structures": [
                {
                    "dimensions": {
                        "series": [
                            {
                                "id": "FREQ",
                                "name": "Frequency",
                                "values": [{"id": "Q", "name": "Quarterly"}],
                            },
                            {
                                "id": "REF_AREA",
                                "name": "Reference area",
                                "values": [
                                    {"id": "USA", "name": "United States"},
                                    {"id": "DEU", "name": "Germany"},
                                ],
                            },
                            {
                                "id": "TRANSFORMATION",
                                "name": "Transformation",
                                "values": [{"id": "GY", "name": "Growth rate"}],
                            },
                        ],
                        "observation": [
                            {
                                "id": "TIME_PERIOD",
                                "name": "Time period",
                                "values": [
                                    {"id": "2023-Q3", "name": "2023-Q3"},
                                    {"id": "2023-Q4", "name": "2023-Q4"},
                                ],
                            }
                        ],
                    }
                }
            ],
            "dataSets": [
                {
                    "series": {
                        "0:0:0": {
                            "observations": {
                                "0": [2.4, 0, 0],
                                "1": [2.5, 0, 0],
                            }
                        },
                        "0:1:0": {
                            "observations": {
                                "0": [0.1, 0, 0],
                                "1": [-0.3, 0, 0],
                            }
                        },
                    }
                }
            ],
        },
    }


def _stored(tmp_path: Path) -> list[StoredArtifact]:
    json_path = tmp_path / "artifacts/data_json/QNA_2023.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(_sdmx_response()))
    return [
        StoredArtifact(
            role="data_json",
            source_url=_url_adapter.validate_python("https://stats.oecd.org/SDMX-JSON/data/QNA"),
            filename="QNA_2023.json",
            relative_path="artifacts/data_json/QNA_2023.json",
            sha256="f" * 64,
            bytes=json_path.stat().st_size,
        )
    ]


def _release() -> DiscoveredRelease:
    artifact = DiscoveredArtifact(
        role="data_json",
        url=_url_adapter.validate_python(
            "https://stats.oecd.org/SDMX-JSON/data/QNA/USA.B1GQ.GY.Q/all"
        ),
        filename="QNA_2023.json",
        link_text="OECD QNA 2023",
    )
    return DiscoveredRelease(
        survey="oecd",
        year=2023,
        landing_page=_url_adapter.validate_python(
            "https://stats.oecd.org/Index.aspx?DatasetCode=QNA"
        ),
        artifacts=[artifact],
        source_metadata={"dataset": "QNA"},
    )


def _adapter() -> OECDAdapter:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=_sdmx_response()))
    )
    return OECDAdapter(definition=_config(), client=client)


def test_oecd_discover_builds_sdmx_url() -> None:
    adapter = _adapter()
    release = adapter.discover(2023)
    assert release.year == 2023
    assert release.artifacts[0].role == "data_json"
    assert "stats.oecd.org/SDMX-JSON/data/QNA" in str(release.artifacts[0].url)
    assert release.source_metadata["api"] == "OECD SDMX-JSON v1"
    assert release.source_metadata["no_registration_required"] is True
    adapter.close()


def test_oecd_validates_and_normalizes(tmp_path: Path) -> None:
    adapter = _adapter()
    release = _release()
    artifacts = _stored(tmp_path)
    result = adapter.validate_release(tmp_path, release, artifacts)
    assert result.passed, {k: v for k, v in result.checks.items() if not v}
    assert result.checks["oecd_benchmark_observation_present"] is True
    assert result.checks["oecd_benchmark_value_matches"] is True

    outputs = adapter.normalize_release(tmp_path, release, artifacts)
    assert len(outputs) == 1
    assert outputs[0].name == "QNA.parquet"
    meta = pq.ParquetFile(outputs[0]).metadata
    assert meta.num_rows == 4  # 2 series x 2 observations
    adapter.close()


def test_oecd_rejects_missing_benchmark(tmp_path: Path) -> None:
    adapter = _adapter()
    release = _release()
    artifacts = _stored(tmp_path)
    # Corrupt the data so the benchmark observation is absent
    data = json.loads((tmp_path / "artifacts/data_json/QNA_2023.json").read_text())
    data["data"]["dataSets"][0]["series"]["0:0:0"]["observations"] = {"0": [9.9, 0, 0]}
    (tmp_path / "artifacts/data_json/QNA_2023.json").write_text(json.dumps(data))

    result = adapter.validate_release(tmp_path, release, artifacts)
    assert not result.passed
    assert result.checks["oecd_benchmark_observation_present"] is False
    adapter.close()
