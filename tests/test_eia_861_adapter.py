"""Tests for the official EIA Form 861 adapter."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.eia_861 import EIA861Adapter
from microdata_lab.models import StoredArtifact

_url = TypeAdapter(AnyHttpUrl)


def _artifact(tmp_path: Path) -> tuple[Path, list[StoredArtifact]]:
    run = tmp_path / "run"
    xlsx = tmp_path / "Sales_Ult_Cust_2024.xlsx"
    rows = pd.DataFrame(
        {
            "Data Year": [2024, 2024, 2024, 2024],
            "Utility Number": [1, 2, 3, 4],
            "Utility Name": ["Municipal", "IOU", "Cooperative", "Federal"],
            "Part": ["A", "A", "A", "A"],
            "Service Type": ["Bundled"] * 4,
            "Data Type\nO = Observed\nI = Imputed": ["O"] * 4,
            "State": ["WA", "WA", "TN", "TN"],
            "Ownership": ["Municipal", "Investor Owned", "Cooperative", "Federal"],
            "BA Code": ["TEST", "TEST", "TVA", "TVA"],
            "Thousand Dollars": [100.0, 200.0, 80.0, 50.0],
            "Megawatthours": [1000.0, 1000.0, 500.0, 250.0],
            "Count": [100, 100, 50, 25],
        }
    )
    with pd.ExcelWriter(xlsx) as writer:
        rows.to_excel(writer, sheet_name="States", startrow=2, index=False)

    archive = run / "artifacts" / "form_861_zip" / "f8612024.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(xlsx, xlsx.name)

    artifact = StoredArtifact(
        role="form_861_zip",
        source_url=_url.validate_python(
            "https://www.eia.gov/electricity/data/eia861/zip/f8612024.zip"
        ),
        filename=archive.name,
        relative_path=str(archive.relative_to(run)),
        sha256="0" * 64,
        bytes=archive.stat().st_size,
    )
    return run, [artifact]


def test_eia_861_discovery_uses_official_release() -> None:
    release = EIA861Adapter().discover(2024)
    assert release.survey == "eia_861"
    assert release.year == 2024
    assert len(release.artifacts) == 1
    assert str(release.artifacts[0].url).startswith("https://www.eia.gov/")


def test_eia_861_validates_and_normalizes(tmp_path: Path) -> None:
    adapter = EIA861Adapter()
    release = adapter.discover(2024)
    run, artifacts = _artifact(tmp_path)

    validation = adapter.validate_release(run, release, artifacts)
    assert validation.passed
    assert validation.checks["ownership_classes_present"]

    outputs = adapter.normalize_release(run, release, artifacts)
    assert len(outputs) == 1
    parquet = pq.ParquetFile(outputs[0])
    assert parquet.metadata.num_rows == 4
    assert parquet.schema.names == [
        "data_year",
        "utility_number",
        "utility_name",
        "service_type",
        "data_type",
        "state",
        "ownership",
        "ba_code",
        "res_revenue_thousand_dollars",
        "res_sales_mwh",
        "res_customers",
    ]
