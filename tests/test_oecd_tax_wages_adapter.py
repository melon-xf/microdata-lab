from __future__ import annotations

import json
from pathlib import Path

import httpx
import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.oecd_tax_wages import (
    OECDTaxWagesAdapter,
    TaxWagesBenchmark,
    TaxWagesConfig,
)
from microdata_lab.models import DiscoveredArtifact, DiscoveredRelease, StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)


def _config() -> TaxWagesConfig:
    return TaxWagesConfig(
        agency="OECD.CTP.TPS",
        flow="DSD_TAX_WAGES_DECOMP@DF_TW_DECOMP",
        version="2.1",
        key="USA+DNK+FIN+NOR+SWE...S_C2+S_C0...A",
        dataset_title="Tax Wages decomposition",
        landing_page=_url_adapter.validate_python(
            "https://data-explorer.oecd.org/vis?df[id]=DSD_TAX_WAGES_DECOMP@DF_TW_DECOMP"
        ),
        reference_year=2025,
        start_period="2024",
        benchmark=TaxWagesBenchmark(
            ref_area="USA",
            measure="AV_TW",
            household_type="S_C0",
            income_principal="AW100",
            time_period="2025",
            expected_value=29.98,
            tolerance=0.5,
        ),
    )


def _sdmx_response() -> dict:
    """Minimal AllDimensions SDMX-JSON: 2 areas x 1 wage level x 2 measures."""
    return {
        "data": {
            "structures": [
                {
                    "dimensions": {
                        "observation": [
                            {
                                "id": "REF_AREA",
                                "values": [
                                    {"id": "USA", "name": "United States"},
                                    {"id": "DNK", "name": "Denmark"},
                                ],
                            },
                            {"id": "FREQ", "values": [{"id": "A", "name": "Annual"}]},
                            {
                                "id": "MEASURE",
                                "values": [{"id": "AV_TW", "name": "Average tax wedge"}],
                            },
                            {
                                "id": "UNIT_MEASURE",
                                "values": [{"id": "PT_COS_LB", "name": "Percent"}],
                            },
                            {
                                "id": "HOUSEHOLD_TYPE",
                                "values": [{"id": "S_C0", "name": "Single, no children"}],
                            },
                            {
                                "id": "INCOME_PRINCIPAL",
                                "values": [{"id": "AW100", "name": "100% of average wage"}],
                            },
                            {"id": "INCOME_SPOUSE", "values": [{"id": "_Z", "name": "None"}]},
                            {"id": "TIME_PERIOD", "values": [{"id": "2025", "name": "2025"}]},
                        ]
                    }
                }
            ],
            "dataSets": [
                {
                    "observations": {
                        "0:0:0:0:0:0:0:0": [29.977066, 0, 0],  # USA AV_TW AW100 2025
                        "1:0:0:0:0:0:0:0": [35.75, 0, 0],  # DNK
                    }
                }
            ],
        }
    }


def _stored(tmp_path: Path) -> list[StoredArtifact]:
    json_path = tmp_path / "artifacts/data_json/tw_2025.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(_sdmx_response()))
    return [
        StoredArtifact(
            role="data_json",
            source_url=_url_adapter.validate_python("https://sdmx.oecd.org/public/rest/data"),
            filename="tw_2025.json",
            relative_path="artifacts/data_json/tw_2025.json",
            sha256="f" * 64,
            bytes=json_path.stat().st_size,
        )
    ]


def _release() -> DiscoveredRelease:
    return DiscoveredRelease(
        survey="oecd_tax_wages",
        year=2025,
        landing_page=_url_adapter.validate_python("https://data-explorer.oecd.org/"),
        artifacts=[
            DiscoveredArtifact(
                role="data_json",
                url=_url_adapter.validate_python(
                    "https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_WAGES_DECOMP@DF_TW_DECOMP,2.1/USA...A"
                ),
                filename="tw_2025.json",
                link_text="OECD Tax Wages 2025",
            )
        ],
        source_metadata={"dataset": "DSD_TAX_WAGES_DECOMP@DF_TW_DECOMP"},
    )


def _adapter() -> OECDTaxWagesAdapter:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=_sdmx_response()))
    )
    return OECDTaxWagesAdapter(definition=_config(), client=client)


def test_tax_wages_discover_builds_sdmx_url() -> None:
    adapter = _adapter()
    release = adapter.discover(2025)
    assert release.year == 2025
    assert "sdmx.oecd.org/public/rest/data" in str(release.artifacts[0].url)
    assert "dimensionAtObservation=AllDimensions" in str(release.artifacts[0].url)
    assert release.source_metadata["api"] == "OECD SDMX 2.1 REST (sdmx.oecd.org/public/rest)"
    adapter.close()


def test_tax_wages_validates_and_normalizes(tmp_path: Path) -> None:
    adapter = _adapter()
    release = _release()
    artifacts = _stored(tmp_path)
    result = adapter.validate_release(tmp_path, release, artifacts)
    assert result.passed, {k: v for k, v in result.checks.items() if not v}
    assert result.checks["oecd_tw_benchmark_value_matches"] is True

    outputs = adapter.normalize_release(tmp_path, release, artifacts)
    assert len(outputs) == 1
    assert outputs[0].name == "tax_wages.parquet"
    meta = pq.ParquetFile(outputs[0]).metadata
    assert meta.num_rows == 2
    adapter.close()


def test_tax_wages_rejects_bad_benchmark(tmp_path: Path) -> None:
    adapter = _adapter()
    release = _release()
    artifacts = _stored(tmp_path)
    data = json.loads((tmp_path / "artifacts/data_json/tw_2025.json").read_text())
    # Change the USA value to 50 (outside tolerance)
    data["data"]["dataSets"][0]["observations"]["0:0:0:0:0:0:0:0"] = [50.0, 0, 0]
    (tmp_path / "artifacts/data_json/tw_2025.json").write_text(json.dumps(data))
    result = adapter.validate_release(tmp_path, release, artifacts)
    assert not result.passed
    assert result.checks["oecd_tw_benchmark_value_matches"] is False
    adapter.close()
