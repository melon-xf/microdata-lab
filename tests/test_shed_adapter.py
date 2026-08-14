from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd
import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.shed import (
    CODEBOOK,
    DATA_CSV_ZIP,
    DATA_STATA_ZIP,
    REPORT,
    SHEDAdapter,
    SHEDBenchmarkDefinition,
    SHEDSourceDefinition,
)
from microdata_lab.models import ArtifactRole, DiscoveredRelease, StoredArtifact

_HTTP_URL = TypeAdapter(AnyHttpUrl)


def _definition() -> SHEDSourceDefinition:
    return SHEDSourceDefinition(
        year=2025,
        landing_page=_HTTP_URL.validate_python("https://www.federalreserve.gov/shed.html"),
        required_roles=[DATA_CSV_ZIP, DATA_STATA_ZIP, CODEBOOK, REPORT],
        expected_rows=4,
        required_columns=[
            "shedid",
            "year",
            "weight",
            "weight_pop",
            "panel_weight",
            "panel_weight_pop",
            "atleast_okay",
        ],
        forbidden_columns=["BK58"],
        benchmark=SHEDBenchmarkDefinition(
            kind="weighted_share",
            variable="atleast_okay",
            values=["Yes"],
            weight="weight",
            expected=0.75,
            absolute_tolerance=0.001,
            source_url=_HTTP_URL.validate_python("https://www.federalreserve.gov/report.html"),
        ),
        report_url=_HTTP_URL.validate_python("https://www.federalreserve.gov/report.pdf"),
        record_unit="adult_respondent",
        universe="U.S. adults",
    )


def test_discovers_complete_official_release() -> None:
    html = """
    <a href="/files/SHED_2025codebook.pdf">Codebook</a>
    <a href="/files/SHED_public_use_data_2025_(CSV).zip">CSV</a>
    <a href="/files/SHED_public_use_data_2025_(STATA).zip">Stata</a>
    <a href="/files/SHED_public_use_data_2019_supplemental_survey_april_2020_(CSV).zip">
      Supplemental CSV
    </a>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://www.federalreserve.gov/shed.html"
        return httpx.Response(200, text=html, request=request)

    adapter = SHEDAdapter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        definition=_definition(),
    )
    try:
        assert adapter.available_years() == [2025]
        release = adapter.discover()
    finally:
        adapter.close()

    assert release.year == 2025
    roles = [
        artifact.role.value if isinstance(artifact.role, ArtifactRole) else artifact.role
        for artifact in release.artifacts
    ]
    assert roles == [DATA_CSV_ZIP, DATA_STATA_ZIP, CODEBOOK, REPORT]
    assert release.source_metadata["cross_section_weight"] == "weight"
    assert release.source_metadata["population_weight"] == "weight_pop"


def test_validation_benchmark_and_parquet_normalization(tmp_path: Path) -> None:
    data = pd.DataFrame(
        {
            "shedid": ["a", "b", "c", "d"],
            "year": [2025, 2025, 2025, 2025],
            "weight": [1.0, 1.0, 1.0, 1.0],
            "weight_pop": [10.0, 20.0, 30.0, 40.0],
            "panel_weight": [0.5, 0.5, None, None],
            "panel_weight_pop": [5.0, 5.0, None, None],
            "atleast_okay": ["Yes", "Yes", "Yes", "No"],
        }
    )
    csv_relative = "extracted/data_csv_zip/public2025.csv"
    dta_relative = "extracted/data_stata_zip/public2025.dta"
    csv_path = tmp_path / csv_relative
    dta_path = tmp_path / dta_relative
    csv_path.parent.mkdir(parents=True)
    dta_path.parent.mkdir(parents=True)
    data.to_csv(csv_path, index=False)
    data.to_stata(dta_path, write_index=False, version=118)

    artifacts = [
        StoredArtifact(
            role=DATA_CSV_ZIP,
            source_url=_HTTP_URL.validate_python("https://www.federalreserve.gov/data.zip"),
            filename="data.zip",
            relative_path="artifacts/data.zip",
            sha256="a" * 64,
            bytes=1,
            extracted_files=[csv_relative],
        ),
        StoredArtifact(
            role=DATA_STATA_ZIP,
            source_url=_HTTP_URL.validate_python("https://www.federalreserve.gov/stata.zip"),
            filename="stata.zip",
            relative_path="artifacts/stata.zip",
            sha256="b" * 64,
            bytes=1,
            extracted_files=[dta_relative],
        ),
    ]
    release = DiscoveredRelease(
        survey="shed",
        year=2025,
        landing_page=_HTTP_URL.validate_python("https://www.federalreserve.gov/shed.html"),
        artifacts=[],
    )
    adapter = SHEDAdapter(client=httpx.Client(), definition=_definition())
    try:
        validation = adapter.validate_release(tmp_path, release, artifacts)
        normalized = adapter.normalize_release(tmp_path, release, artifacts)
    finally:
        adapter.close()

    assert validation.passed
    assert validation.checks["shed_official_benchmark"]
    assert "benchmark_observed=0.75000000" in validation.notes
    assert len(normalized) == 1
    table = pq.read_table(normalized[0])
    assert table.num_rows == 4
    assert table.num_columns == 7


def test_removed_bk58_variable_fails_validation(tmp_path: Path) -> None:
    definition = _definition()
    data = pd.DataFrame(
        {
            "shedid": ["a", "b", "c", "d"],
            "year": [2025] * 4,
            "weight": [1.0] * 4,
            "weight_pop": [10.0] * 4,
            "panel_weight": [1.0] * 4,
            "panel_weight_pop": [10.0] * 4,
            "atleast_okay": ["Yes", "Yes", "Yes", "No"],
            "BK58": [0, 0, 0, 0],
        }
    )
    csv_relative = "extracted/data_csv_zip/public2025.csv"
    dta_relative = "extracted/data_stata_zip/public2025.dta"
    csv_path = tmp_path / csv_relative
    dta_path = tmp_path / dta_relative
    csv_path.parent.mkdir(parents=True)
    dta_path.parent.mkdir(parents=True)
    data.to_csv(csv_path, index=False)
    data.drop(columns=["BK58"]).to_stata(dta_path, write_index=False, version=118)
    artifacts = [
        StoredArtifact(
            role=DATA_CSV_ZIP,
            source_url=_HTTP_URL.validate_python("https://www.federalreserve.gov/data.zip"),
            filename="data.zip",
            relative_path="artifacts/data.zip",
            sha256="a" * 64,
            bytes=1,
            extracted_files=[csv_relative],
        ),
        StoredArtifact(
            role=DATA_STATA_ZIP,
            source_url=_HTTP_URL.validate_python("https://www.federalreserve.gov/stata.zip"),
            filename="stata.zip",
            relative_path="artifacts/stata.zip",
            sha256="b" * 64,
            bytes=1,
            extracted_files=[dta_relative],
        ),
    ]
    release = DiscoveredRelease(
        survey="shed",
        year=2025,
        landing_page=_HTTP_URL.validate_python("https://www.federalreserve.gov/shed.html"),
        artifacts=[],
    )
    adapter = SHEDAdapter(client=httpx.Client(), definition=definition)
    try:
        validation = adapter.validate_release(tmp_path, release, artifacts)
    finally:
        adapter.close()

    assert not validation.passed
    assert not validation.checks["shed_removed_columns_absent"]
